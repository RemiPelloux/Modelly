"""Bass diffusion: the adoption curve against the Bass equation, and same seed same run."""

import numpy as np
import pytest

from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario, bass_curve

P, Q, DT, STEPS = 0.03, 0.38, 0.1, 200
# Five standard deviations of the linear-noise approximation, at every one of the steps.
Z_BOUND = 5.0
# A non-adopter on a sparse network sees clustered non-adopters: adoption lags the
# well-mixed curve by far more than this many standard deviations at mid-diffusion.
LAG_BOUND = 3.0
MIDPOINT = STEPS // 2


def recursion(households):
    """Mean-field recursion of the simulation and the variance of its noise.

    ``F_{k+1} = F_k + (1 - F_k) h_k`` with ``h_k = (p + q F_k) dt``. Linearising around it,
    a deviation grows by ``1 + f'(F_k)`` per step, ``f(F) = (1 - F)(p + q F) dt``, and the
    step adds binomial noise of variance ``(1 - F_k) h_k (1 - h_k) / N``.
    """
    mean, var = [0.0], [0.0]
    for _ in range(STEPS):
        f = mean[-1]
        h = (P + Q * f) * DT
        slope = (Q * (1 - f) - (P + Q * f)) * DT
        var.append((1 + slope) ** 2 * var[-1] + (1 - f) * h * (1 - h) / households)
        mean.append(f + (1 - f) * h)
    return np.array(mean), np.array(var)


def curve(households, **params):
    """Time and adoption share of one run."""
    scenario = BassScenario(households=households, steps=STEPS, dt=DT, **params)
    model = BassDiffusion(scenario)
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    return frame["time"].to_numpy(), frame["adoption"].to_numpy()


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_well_mixed_follows_bass_equation(seed):
    """``|F_sim - F_ode| <= Euler error + 5 sd`` at every step."""
    households = 5000
    time, adoption = curve(households, rng=seed)
    mean, var = recursion(households)
    ode = bass_curve(time, P, Q)
    euler = np.abs(mean - ode)
    assert np.all(np.abs(adoption - ode) <= euler + Z_BOUND * np.sqrt(var))
    assert adoption[-1] > ode[MIDPOINT]  # the curve went well past its midpoint


def test_dense_network_is_close_to_well_mixed():
    """With 50 neighbours each, the network share is close to the population share."""
    households = 2000
    time, adoption = curve(households, rng=4, mixing="network", degree=50)
    mean, var = recursion(households)
    euler = np.abs(mean - bass_curve(time, P, Q))
    assert np.all(
        np.abs(adoption - bass_curve(time, P, Q)) <= euler + Z_BOUND * np.sqrt(var)
    )


def test_sparse_network_adopts_more_slowly():
    """With four neighbours each, adoption at mid-diffusion lags the well-mixed curve."""
    households = 2000
    _, adoption = curve(households, rng=5, mixing="network", degree=4)
    mean, var = recursion(households)
    assert adoption[MIDPOINT] < mean[MIDPOINT] - LAG_BOUND * np.sqrt(var[MIDPOINT])


def test_adoption_never_reverts():
    """Adoption is monotone and every household ends up counted once."""
    _, adoption = curve(1000, rng=6, mixing="network", degree=6)
    assert np.all(np.diff(adoption) >= 0)
    assert 0 <= adoption[0] <= adoption[-1] <= 1


def test_unknown_mixing_is_rejected():
    """``mixing`` is ``"well-mixed"`` or ``"network"``."""
    with pytest.raises(ValueError, match="mixing"):
        BassDiffusion(BassScenario(rng=1, mixing="ring"))


def test_same_seed_same_run():
    """Same seed, same curve; another seed, another curve."""
    params = {"mixing": "network", "degree": 6}
    assert np.array_equal(
        curve(800, rng=7, **params)[1], curve(800, rng=7, **params)[1]
    )
    assert not np.array_equal(
        curve(800, rng=7, **params)[1], curve(800, rng=8, **params)[1]
    )
