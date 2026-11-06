"""Philox4x32-10: the counter-based generator every Modelly backend draws from.

A counter-based generator maps a 128-bit counter and a 64-bit key to 128 random
bits with no state in between (Salmon, Moraes, Dror and Shaw, "Parallel random
numbers: as easy as 1, 2, 3", SC 2011). Any element of any stream can therefore
be computed on its own, on any device, in any order: the numbers a GPU draws
for agent ``i`` are the numbers the CPU draws for agent ``i``.

``philox4x32`` here is written once against the array API (``xp`` is numpy,
CuPy or ``jax.numpy``) and checked against the published known-answer vectors
of the Random123 library. Numpy's own ``numpy.random.Philox`` is the 4x64
variant, so its streams are not these. The CuPy backend runs the same rounds as
CUDA kernels (``CUDA_PHILOX``), checked bit for bit against this one.

Two ways to compute the high half of a 32 x 32-bit product: in 64-bit integers
(numpy, CuPy, JAX with ``jax_enable_x64``), or from 16-bit halves in 32-bit
integers (JAX without 64-bit types). Both give the same bits.
"""

from __future__ import annotations

from collections.abc import Iterator
from numbers import Integral
from typing import Any

import numpy as np

ROUNDS = 10
MULTIPLIERS = (0xD2511F53, 0xCD9E8D57)
WEYL = (0x9E3779B9, 0xBB67AE85)
WORD_BITS = 32
HALF_BITS = 16
WORD_MASK = 0xFFFFFFFF
HALF_MASK = 0xFFFF
WORDS = 4

# The same rounds in CUDA C, as a device function for the CuPy kernels.
CUDA_PHILOX = """
__device__ void modelly_philox(unsigned int x[4], unsigned int key0, unsigned int key1) {
    for (int r = 0; r < 10; ++r) {
        unsigned int hi0 = __umulhi(0xD2511F53u, x[0]), lo0 = 0xD2511F53u * x[0];
        unsigned int hi1 = __umulhi(0xCD9E8D57u, x[2]), lo1 = 0xCD9E8D57u * x[2];
        unsigned int y0 = hi1 ^ x[1] ^ key0, y2 = hi0 ^ x[3] ^ key1;
        x[0] = y0; x[1] = lo1; x[2] = y2; x[3] = lo0;
        key0 += 0x9E3779B9u; key1 += 0xBB67AE85u;
    }
}
"""


def mulhilo_wide(a: Any, b: Any, xp: Any) -> tuple[Any, Any]:
    """High and low words of ``a * b`` for uint32 arrays, through 64-bit integers."""
    product = xp.asarray(a, dtype=xp.uint64) * xp.asarray(b, dtype=xp.uint64)
    high = (product >> WORD_BITS).astype(xp.uint32)
    low = (product & WORD_MASK).astype(xp.uint32)
    return high, low


def mulhilo_narrow(a: Any, b: Any, xp: Any) -> tuple[Any, Any]:
    """High and low words of ``a * b`` for uint32 arrays, from 16-bit halves only."""
    a = xp.asarray(a, dtype=xp.uint32)
    b = xp.asarray(b, dtype=xp.uint32)
    a_hi, a_lo = a >> HALF_BITS, a & HALF_MASK
    b_hi, b_lo = b >> HALF_BITS, b & HALF_MASK
    lo_lo, lo_hi = a_lo * b_lo, a_lo * b_hi
    hi_lo, hi_hi = a_hi * b_lo, a_hi * b_hi
    middle = (lo_lo >> HALF_BITS) + (lo_hi & HALF_MASK) + (hi_lo & HALF_MASK)
    high = hi_hi + (lo_hi >> HALF_BITS) + (hi_lo >> HALF_BITS) + (middle >> HALF_BITS)
    return high, a * b


def philox4x32(
    counter: tuple[Any, Any, Any, Any], key: tuple[int, int], xp: Any, wide: bool = True
) -> tuple[Any, Any, Any, Any]:
    """The four output words of Philox4x32-10 for every counter.

    Args:
        counter: four uint32 words; arrays broadcast against each other.
        key: two 32-bit integers (or two uint32 arrays, such as a traced JAX key).
        xp: the array namespace (numpy, CuPy or ``jax.numpy``).
        wide: multiply through 64-bit integers; ``False`` for 32-bit-only JAX.

    Returns:
        Four uint32 arrays of the broadcast shape of ``counter``.
    """
    mulhilo = mulhilo_wide if wide else mulhilo_narrow
    x0, x1, x2, x3 = (xp.asarray(word, dtype=xp.uint32) for word in counter)
    x0, x1, x2, x3 = xp.broadcast_arrays(x0, x1, x2, x3)
    m0 = xp.asarray(MULTIPLIERS[0], dtype=xp.uint32)
    m1 = xp.asarray(MULTIPLIERS[1], dtype=xp.uint32)
    for k0, k1 in _round_keys(key, xp):
        hi0, lo0 = mulhilo(m0, x0, xp)
        hi1, lo1 = mulhilo(m1, x2, xp)
        x0, x1, x2, x3 = hi1 ^ x1 ^ k0, lo1, hi0 ^ x3 ^ k1, lo0
    return x0, x1, x2, x3


def _philox4x32_numpy(
    counter: tuple[Any, Any, Any, Any], key: tuple[int, int]
) -> tuple[Any, Any, Any, Any]:
    """``philox4x32`` for numpy, in place on four word arrays and two product buffers.

    Integer operations only, so the bits are those of ``philox4x32``; the rounds allocate
    nothing.
    """
    words = np.broadcast_arrays(*(np.asarray(w, dtype=np.uint32) for w in counter))
    x0, x1, x2, x3 = (np.array(w, dtype=np.uint32) for w in words)
    product0, product1 = np.empty(x0.shape, np.uint64), np.empty(x0.shape, np.uint64)
    high = np.empty(x0.shape, np.uint64)
    m0, m1 = np.uint64(MULTIPLIERS[0]), np.uint64(MULTIPLIERS[1])
    shift = np.uint64(WORD_BITS)
    for k0, k1 in _round_keys(key, np):
        np.multiply(x0, m0, out=product0)
        np.multiply(x2, m1, out=product1)
        np.right_shift(product1, shift, out=high)
        np.bitwise_xor(x1, high, out=x0, casting="unsafe")  # the high word fits
        x0 ^= k0
        np.copyto(x1, product1, casting="unsafe")  # the low word: modulo 2**32
        np.right_shift(product0, shift, out=high)
        np.bitwise_xor(x3, high, out=x2, casting="unsafe")
        x2 ^= k1
        np.copyto(x3, product0, casting="unsafe")
    return x0, x1, x2, x3


def _round_keys(key: tuple[Any, Any], xp: Any) -> Iterator[tuple[Any, Any]]:
    """The key words of each round, as uint32: the key plus ``WEYL`` per round, mod ``2**32``.

    Integer keys are masked and stepped as Python integers; uint32 array keys (a key traced
    by ``jax.jit``) are stepped in uint32, whose addition wraps to the same words.
    """
    if isinstance(key[0], Integral) and isinstance(key[1], Integral):
        key0, key1 = int(key[0]) & WORD_MASK, int(key[1]) & WORD_MASK
        for _ in range(ROUNDS):
            yield xp.asarray(key0, dtype=xp.uint32), xp.asarray(key1, dtype=xp.uint32)
            key0, key1 = (key0 + WEYL[0]) & WORD_MASK, (key1 + WEYL[1]) & WORD_MASK
        return
    key0, key1 = (xp.asarray(word, dtype=xp.uint32) for word in key)
    weyl0, weyl1 = (xp.asarray(word, dtype=xp.uint32) for word in WEYL)
    for _ in range(ROUNDS):
        yield key0, key1
        key0, key1 = key0 + weyl0, key1 + weyl1


def philox4x32_reference(counter: tuple[int, ...], key: tuple[int, int]) -> tuple:
    """Philox4x32-10 for one counter in Python integers: the reference of the others."""
    x0, x1, x2, x3 = counter
    key0, key1 = key
    for _ in range(ROUNDS):
        p0, p1 = MULTIPLIERS[0] * x0, MULTIPLIERS[1] * x2
        x0, x1, x2, x3 = (
            (p1 >> WORD_BITS) ^ x1 ^ key0,
            p1 & WORD_MASK,
            (p0 >> WORD_BITS) ^ x3 ^ key1,
            p0 & WORD_MASK,
        )
        key0, key1 = (key0 + WEYL[0]) & WORD_MASK, (key1 + WEYL[1]) & WORD_MASK
    return x0, x1, x2, x3
