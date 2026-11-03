"""SDEs: strong orders measured on geometric Brownian motion, seeded noise, checkpoints."""

import numpy as np
import pytest

from modelly import Agent, Model
from modelly.core.columns import Column
from modelly.couple.agent_sde import AgentSDE
from modelly.couple.schedule import CouplingError
from modelly.couple.sde import coarsen, increments, solve_sde_batch

MU, SIGMA, X0, T = 2.0, 1.0, 1.0, 1.0
PATHS = 4000
FINE = 2**10  # steps of the reference Brownian path
FACTORS = (4, 8, 16, 32, 64)


def drift(t, y, p):
    """GBM drift ``mu y``."""
    return MU * y


def diffusion(t, y, p):
    """GBM noise ``sigma y``."""
    return SIGMA * y


def strong_errors(scheme):
    """``E |X_T - exact|`` for each step, every scheme driven by one Brownian path per run."""
    rng = np.random.default_rng(100)
    times = np.linspace(0.0, T, FINE + 1)
    dws = increments(rng, (1, PATHS), times)
    exact = X0 * np.exp((MU - SIGMA**2 / 2) * T + SIGMA * dws.sum(axis=0))
    errors = []
    for factor in FACTORS:
        y = solve_sde_batch(drift, diffusion, (0.0, T), np.full((1, PATHS), X0),
                            dt=T * factor / FINE, scheme=scheme, noise=coarsen(dws, factor)).y  # fmt: skip
        errors.append(np.mean(np.abs(y - exact)))
    return np.array(errors)


@pytest.mark.parametrize(("scheme", "order"), [("euler", 0.5), ("milstein", 1.0)])
def test_strong_order_on_geometric_brownian_motion(scheme, order):
    """The error falls as ``dt**order``: one half for Euler-Maruyama, one for Milstein."""
    steps = T * np.array(FACTORS) / FINE
    slope = np.polyfit(np.log(steps), np.log(strong_errors(scheme)), 1)[0]
    assert slope == pytest.approx(order, abs=0.12)


def test_euler_mean_matches_the_exact_mean():
    """``E[X_T] = X0 exp(mu T)``, within four standard errors, on a fine step."""
    mu, sigma = 0.5, 0.3
    y = solve_sde_batch(lambda t, y, p: mu * y, lambda t, y, p: sigma * y, (0.0, 1.0),
                        np.ones((1, 20_000)), dt=1e-3, rng=np.random.default_rng(5)).y  # fmt: skip
    se = y.std() / np.sqrt(y.size)
    assert abs(y.mean() - np.exp(mu)) < 4 * se


def test_without_noise_it_is_the_euler_method():
    """``diffusion = 0`` gives ``(1 - dt)**n`` for ``y' = -y``, whatever the generator."""
    y = solve_sde_batch(lambda t, y, p: -y, lambda t, y, p: 0.0, (0.0, 1.0), np.ones((2, 3)),
                        dt=0.1, rng=np.random.default_rng(1), keep_path=True)  # fmt: skip
    np.testing.assert_allclose(y.y, 0.9**10)
    assert y.path.shape == (11, 2, 3) and y.t[-1] == 1.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [({"scheme": "heun", "rng": 1}, "supports"), ({"dt": 0.0, "rng": 1}, "positive"),
     ({}, "rng= or noise="), ({"noise": np.zeros((3, 1, 1))}, "increments of shape")],
)  # fmt: skip
def test_bad_arguments_are_refused(kwargs, match):
    """Each mistake is named."""
    kwargs = {"dt": 0.1, **kwargs}
    if kwargs.get("rng") == 1:
        kwargs["rng"] = np.random.default_rng(1)
    with pytest.raises(CouplingError, match=match):
        solve_sde_batch(drift, diffusion, (0.0, 1.0), np.ones((1, 1)), **kwargs)


class Firm(Agent):
    """A firm whose capital follows geometric Brownian motion."""

    capital = Column(float, default=1.0)
    volatility = Column(float, default=0.2)


def growth(t, y, p):
    """Five per cent drift."""
    return 0.05 * y


def shocks(t, y, p):
    """Each firm's own volatility."""
    return p["volatility"] * y


class Economy(Model):
    """Firms with stochastic capital; another phase draws from the same generator."""

    def __init__(self, rng=9):
        """Fifty firms with different volatilities."""
        super().__init__(rng=rng)
        Firm.create_agents(self, 50)
        self.columns[Firm].volatility[:] = np.linspace(0.05, 0.5, 50)
        self.sde = AgentSDE(self, Firm, growth, shocks, ["capital"], ["volatility"],
                            dt=0.05, scheme="milstein")  # fmt: skip

    def step(self):
        """A draw for something else, then one unit of time of the firms."""
        self.rng.random()
        self.sde.advance(float(self.time), 1.0)


def test_same_seed_same_capital_and_a_resumed_run_equals_a_straight_one(tmp_path):
    """The noise is the model's: one seed, one path, saved and loaded included."""
    straight = Economy()
    straight.run_for(8)
    again = Economy()
    again.run_for(8)
    np.testing.assert_array_equal(
        again.columns[Firm].capital, straight.columns[Firm].capital
    )
    resumed = Economy()
    resumed.run_for(3)
    resumed.save(tmp_path / "economy.ckpt")
    loaded = Economy.load(tmp_path / "economy.ckpt")
    loaded.run_for(5)
    np.testing.assert_array_equal(
        loaded.columns[Firm].capital, straight.columns[Firm].capital
    )
    other = Economy(rng=10)
    other.run_for(8)
    assert not np.array_equal(
        other.columns[Firm].capital, straight.columns[Firm].capital
    )
