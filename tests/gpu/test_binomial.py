"""Binomial variates from Philox: the law (chi-square against the pmf) and cross-backend equality."""

import numpy as np
import pytest
from scipy import stats

from modelly.gpu import PhiloxStream
from modelly.gpu.binomial import TAIL_TABLE

SEED = 11
SAMPLES = 40_000
ALPHA = 1e-4  # a correct sampler fails one case in ten thousand


def chi_square_p(values, n, p):
    """p-value of the observed counts against Binomial(n, p), sparse bins pooled."""
    support = np.arange(n + 1)
    expected = stats.binom.pmf(support, n, p) * len(values)
    observed = np.bincount(values, minlength=n + 1)
    keep = expected >= 5
    pooled_expected = np.append(expected[keep], expected[~keep].sum())
    pooled_observed = np.append(observed[keep], observed[~keep].sum())
    if pooled_expected[-1] < 5:
        pooled_expected, pooled_observed = pooled_expected[:-1], pooled_observed[:-1]
        pooled_expected *= pooled_observed.sum() / pooled_expected.sum()
    return stats.chisquare(pooled_observed, pooled_expected).pvalue


@pytest.mark.parametrize(
    ("n", "p"),
    [
        (1, 0.5),
        (12, 0.3),
        (40, 0.2),
        (30, 0.6),
        (200, 0.3),
        (5000, 0.02),
        (1000, 0.9),
        (80, 0.5),
    ],
)
def test_binomial_law(n, p):
    """Inversion (mean < 10) and BTRS (mean >= 10) follow Binomial(n, p)."""
    values = PhiloxStream(SEED).binomial(np.full(SAMPLES, n), p)
    assert values.min() >= 0 and values.max() <= n
    assert chi_square_p(values, n, p) > ALPHA


def test_huge_counts_have_the_right_mean_and_variance():
    """Counts in the millions: sample mean and variance near n p and n p (1 - p)."""
    n, p = 3_000_000, 0.37
    values = PhiloxStream(SEED).binomial(np.full(SAMPLES, n), p).astype(float)
    spread = np.sqrt(n * p * (1 - p))
    assert abs(values.mean() - n * p) < 5 * spread / np.sqrt(SAMPLES)
    assert abs(values.var() / (n * p * (1 - p)) - 1) < 0.05


def test_edges():
    """Zero counts, p = 0 and p = 1 are exact; per-element p broadcasts."""
    stream = PhiloxStream(SEED)
    counts = np.array([0, 5, 7, 9, 100])
    out = stream.binomial(counts, np.array([0.5, 0.0, 1.0, 0.5, 1.0]))
    assert out[0] == 0 and out[1] == 0 and out[2] == 7 and out[4] == 100
    assert 0 <= out[3] <= 9
    assert stream.binomial(np.array([], dtype=np.int64), 0.5).shape == (0,)


def test_tail_table_is_the_stirling_correction():
    """The tabulated corrections are those of Hörmann's algorithm (to 1e-12)."""
    hormann = [0.0810614667953272, 0.0413406959554092, 0.0276779256849983]
    assert np.allclose(TAIL_TABLE[:3], hormann, rtol=0, atol=1e-12)


def test_positions_make_batches_and_subsets_agree():
    """A batch drawn at its offset gives the variates of the same rows drawn at once."""
    counts = np.random.default_rng(1).integers(0, 400, 3000)
    draw = PhiloxStream(SEED).draws()
    whole = draw.binomial(counts, 0.4)
    tail = draw.binomial(counts[1000:], 0.4, start=1000)
    assert np.array_equal(whole[1000:], tail)


MIXED_COUNTS = np.array([0, 1, 5, 30, 100, 1000, 100_000, 7, 50, 3, 12] * 300)
MIXED_P = np.array([0.3, 0.3, 0.9, 0.2, 0.5, 0.01, 0.4, 1.0, 0.0, 0.7, 0.95] * 300)


def test_gpu_backends_give_numpy_variates(other_backend):
    """Same seed, same variates on CuPy and (64-bit) JAX, for both samplers."""
    expected = PhiloxStream(SEED).binomial(MIXED_COUNTS, MIXED_P)
    got = PhiloxStream(SEED, 0, other_backend).binomial(MIXED_COUNTS, MIXED_P)
    assert np.array_equal(other_backend.to_numpy(got), expected)


def test_jax_32_bit_binomials_follow_the_law(jax_backend):
    """32-bit JAX draws other variates (float32 uniforms), from the same law."""
    values = PhiloxStream(SEED, 0, jax_backend).binomial(np.full(SAMPLES, 200), 0.3)
    assert chi_square_p(jax_backend.to_numpy(values), 200, 0.3) > ALPHA
