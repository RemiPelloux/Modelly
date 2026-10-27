"""Philox4x32-10 against the Random123 known-answer vectors and across backends."""

import numpy as np
import pytest

from modelly.gpu.philox import (
    mulhilo_narrow,
    mulhilo_wide,
    philox4x32,
    philox4x32_reference,
)

# Random123 kat_vectors, philox4x32 with 10 rounds: counter, key, expected output.
KNOWN_ANSWERS = [
    ((0, 0, 0, 0), (0, 0), (0x6627E8D5, 0xE169C58D, 0xBC57AC4C, 0x9B00DBD8)),
    (
        (0xFFFFFFFF,) * 4,
        (0xFFFFFFFF,) * 2,
        (0x408F276D, 0x41C83B0E, 0xA20BC7C6, 0x6D5451FD),
    ),
    (
        (0x243F6A88, 0x85A308D3, 0x13198A2E, 0x03707344),
        (0xA4093822, 0x299F31D0),
        (0xD16CFE09, 0x94FDCCEB, 0x5001E420, 0x24126EA1),
    ),
]


@pytest.mark.parametrize(("counter", "key", "expected"), KNOWN_ANSWERS)
def test_reference_matches_random123(counter, key, expected):
    """The Python-integer reference gives the published outputs."""
    assert philox4x32_reference(counter, key) == expected


@pytest.mark.parametrize("wide", [True, False])
@pytest.mark.parametrize(("counter", "key", "expected"), KNOWN_ANSWERS)
def test_numpy_rounds_match_random123(counter, key, expected, wide):
    """The array version gives them too, through 64-bit and through 16-bit products."""
    words = tuple(np.array([c], dtype=np.uint32) for c in counter)
    out = philox4x32(words, key, np, wide=wide)
    assert tuple(int(w[0]) for w in out) == expected


def test_narrow_product_equals_wide():
    """The 16-bit-halves product gives the bits of the 64-bit product."""
    rng = np.random.default_rng(3)
    a = rng.integers(0, 2**32, 10_000, dtype=np.uint64).astype(np.uint32)
    b = rng.integers(0, 2**32, 10_000, dtype=np.uint64).astype(np.uint32)
    edges = np.array([0, 1, 0xFFFF, 0x10000, 0xFFFFFFFF], dtype=np.uint32)
    a, b = np.concatenate([a, edges, edges]), np.concatenate([b, edges, edges[::-1]])
    with np.errstate(over="ignore"):
        narrow = mulhilo_narrow(a, b, np)
    wide = mulhilo_wide(a, b, np)
    assert np.array_equal(narrow[0], wide[0]) and np.array_equal(narrow[1], wide[1])


def test_array_version_matches_reference_on_many_counters():
    """Every lane of a batch equals the reference for its own counter."""
    block = np.arange(0, 2**32 - 1, 2**32 // 257, dtype=np.uint64).astype(np.uint32)
    out = philox4x32((block, 7, 11, 13), (123456789, 987654321), np)
    for i in (0, 1, 100, len(block) - 1):
        expected = philox4x32_reference(
            (int(block[i]), 7, 11, 13), (123456789, 987654321)
        )
        assert tuple(int(w[i]) for w in out) == expected


def test_gpu_backends_give_the_numpy_bits(other_backend):
    """CuPy's kernel and JAX's jitted rounds give numpy's words, bit for bit."""
    block = np.arange(100_000, dtype=np.uint32)
    words, key = (5, 6, 7), (0xDEADBEEF, 42)
    expected = philox4x32((block, *words), key, np)
    got = other_backend.philox(other_backend.asarray(block), words, key)
    for mine, theirs in zip(got, expected):
        assert np.array_equal(other_backend.to_numpy(mine), theirs)


def test_jax_without_x64_gives_the_numpy_bits(jax_backend):
    """32-bit JAX multiplies through 16-bit halves and still gives numpy's words."""
    assert not jax_backend.wide
    block = np.arange(50_000, dtype=np.uint32)
    expected = philox4x32((block, 1, 2, 3), (9, 10), np)
    got = jax_backend.philox(jax_backend.asarray(block), (1, 2, 3), (9, 10))
    for mine, theirs in zip(got, expected):
        assert np.array_equal(jax_backend.to_numpy(mine), theirs)
