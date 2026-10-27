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

from typing import Any

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
        key: two 32-bit integers.
        xp: the array namespace (numpy, CuPy or ``jax.numpy``).
        wide: multiply through 64-bit integers; ``False`` for 32-bit-only JAX.

    Returns:
        Four uint32 arrays of the broadcast shape of ``counter``.
    """
    mulhilo = mulhilo_wide if wide else mulhilo_narrow
    x0, x1, x2, x3 = (xp.asarray(word, dtype=xp.uint32) for word in counter)
    x0, x1, x2, x3 = xp.broadcast_arrays(x0, x1, x2, x3)
    key0, key1 = key[0] & WORD_MASK, key[1] & WORD_MASK
    m0 = xp.asarray(MULTIPLIERS[0], dtype=xp.uint32)
    m1 = xp.asarray(MULTIPLIERS[1], dtype=xp.uint32)
    for _ in range(ROUNDS):
        hi0, lo0 = mulhilo(m0, x0, xp)
        hi1, lo1 = mulhilo(m1, x2, xp)
        k0 = xp.asarray(key0, dtype=xp.uint32)
        k1 = xp.asarray(key1, dtype=xp.uint32)
        x0, x1, x2, x3 = hi1 ^ x1 ^ k0, lo1, hi0 ^ x3 ^ k1, lo0
        key0, key1 = (key0 + WEYL[0]) & WORD_MASK, (key1 + WEYL[1]) & WORD_MASK
    return x0, x1, x2, x3


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
