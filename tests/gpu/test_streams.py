"""PhiloxStream: draws addressed by position, the same on every backend."""

import pickle

import numpy as np
import pytest

from modelly.gpu import PhiloxStream
from modelly.gpu.philox import philox4x32_reference

SEED, STREAM = 20260427, 3


def test_words_are_philox_at_the_documented_counter():
    """Element i of draw c is word i % 4 of the block (i // 4, 0, c, stream)."""
    stream = PhiloxStream(SEED, STREAM)
    stream.draws()  # draw 0 is skipped: the second draw has call number 1
    bits = stream.draws().bits(10)
    key = (SEED & 0xFFFFFFFF, SEED >> 32)
    for i in (0, 3, 4, 9):
        block = philox4x32_reference((i // 4, 0, 1, STREAM), key)
        assert int(bits[i]) == block[i % 4]


def test_float64_uniforms_take_53_bits_from_two_words():
    """A float64 uniform is ((w0 >> 5) * 2**26 + (w1 >> 6)) / 2**53, numpy's construction."""
    draw = PhiloxStream(SEED).draws()
    words = draw.words(3, per_element=2)
    u = draw.random(3)
    expected = ((words[:, 0] >> 5) * 2.0**26 + (words[:, 1] >> 6)) / 2.0**53
    assert np.array_equal(u, expected)
    assert u.dtype == np.float64 and ((u >= 0) & (u < 1)).all()


def test_batches_and_positions_give_the_whole_draw():
    """A draw read in batches, or at shuffled positions, gives the same numbers."""
    draw = PhiloxStream(SEED).draws()
    whole = draw.random(1001)
    parts = np.concatenate([draw.random(333), draw.random(668, start=333)])
    positions = np.random.default_rng(0).permutation(1001)
    assert np.array_equal(whole, parts)
    assert np.array_equal(draw.random_at(positions), whole[positions])
    single = draw.random(1001, dtype=np.float32)
    assert np.array_equal(
        draw.random_at(positions, dtype=np.float32), single[positions]
    )


def test_successive_draws_and_streams_differ():
    """Each call is a new draw; another stream of the same seed is another sequence."""
    stream = PhiloxStream(SEED)
    first, second = stream.random(100), stream.random(100)
    other = stream.spawn(STREAM + 1).random(100)
    assert not np.array_equal(first, second) and not np.array_equal(first, other)
    assert stream.calls == 2


def test_integers_are_bounded_and_nearly_uniform():
    """``integers(high)`` stays in [0, high) and fills it evenly."""
    stream = PhiloxStream(SEED)
    values = stream.integers(np.full(60_000, 6))
    counts = np.bincount(values, minlength=6)
    assert values.min() == 0 and values.max() == 5
    assert np.all(np.abs(counts / 10_000 - 1) < 0.05)


def test_bernoulli_frequency_and_shapes():
    """Bernoulli draws hit p on average; a scalar p needs n."""
    stream = PhiloxStream(SEED)
    hits = stream.bernoulli(np.full(100_000, 0.3))
    assert abs(hits.mean() - 0.3) < 0.01
    assert stream.bernoulli(0.5, n=7).shape == (7,)


def test_seed_and_stream_limits():
    """Negative seeds and streams beyond 32 bits are refused."""
    with pytest.raises(ValueError):
        PhiloxStream(-1)
    with pytest.raises(ValueError):
        PhiloxStream(1, stream=2**32)
    with pytest.raises(ValueError):
        PhiloxStream(2**64)


def test_pickle_keeps_the_position_in_the_stream():
    """A pickled stream continues where it was, on the backend of the same name."""
    stream = PhiloxStream(SEED)
    stream.random(5)
    copy = pickle.loads(pickle.dumps(stream))  # noqa: S301 - our own bytes
    assert copy.calls == 1 and copy.backend.name == "numpy"
    assert np.array_equal(copy.random(5), stream.random(5))
    assert "calls=2" in repr(stream)


def test_empty_draws():
    """Zero elements give empty arrays."""
    stream = PhiloxStream(SEED)
    assert stream.random(0).shape == (0,)
    assert stream.draws().bits(0).shape == (0,)


DRAWS = {
    "random": lambda s: s.random(10_001),
    "random32": lambda s: s.random(10_001, dtype=np.float32),
    "bits": lambda s: s.draws().bits(9_999, start=13),
    "integers": lambda s: s.integers(np.arange(1, 5_000)),
    "random_at": lambda s: s.draws().random_at(np.array([7, 3, 70_000, 2])),
    "bernoulli": lambda s: s.bernoulli(np.linspace(0, 1, 4_001)),
}


@pytest.mark.parametrize("kind", list(DRAWS))
def test_gpu_backends_draw_numpy_numbers(other_backend, kind):
    """CuPy and (64-bit) JAX draw exactly numpy's numbers for the same seed and stream."""
    draw = DRAWS[kind]
    expected = draw(PhiloxStream(SEED, STREAM))
    got = other_backend.to_numpy(draw(PhiloxStream(SEED, STREAM, other_backend)))
    assert got.dtype.kind == expected.dtype.kind
    assert np.array_equal(got, expected)


def test_jax_32_bit_uniforms_are_numpy_float32(jax_backend):
    """Without x64, JAX's uniforms are float32 and equal numpy's float32 uniforms."""
    got = PhiloxStream(SEED, STREAM, jax_backend).random(5_000)
    expected = PhiloxStream(SEED, STREAM).random(5_000, dtype=np.float32)
    assert str(got.dtype) == "float32"
    assert np.array_equal(jax_backend.to_numpy(got), expected)
    ints = PhiloxStream(SEED, STREAM, jax_backend).integers(np.arange(1, 999))
    assert np.array_equal(
        jax_backend.to_numpy(ints),
        PhiloxStream(SEED, STREAM).integers(np.arange(1, 999)),
    )
