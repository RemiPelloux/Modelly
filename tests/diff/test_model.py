"""DiffModel: phases traced by JAX, the differentiable flag, estimators and gradient checks."""

import numpy as np
import pytest

jax = pytest.importorskip("jax")
jnp = jax.numpy

from modelly.diff import (  # noqa: E402
    GUMBEL_SOFTMAX,
    SCORE_FUNCTION,
    STRAIGHT_THROUGH,
    DiffModel,
    DiffRandom,
    GradientApproximationWarning,
    check_gradients,
    phase,
)
from modelly.zoo.bass_diffusion.differentiable import (  # noqa: E402
    differentiable_model as bass_model,
)
from modelly.zoo.bouchaud_mezard.differentiable import (  # noqa: E402
    differentiable_model as wealth_model,
)
from modelly.zoo.bouchaud_mezard.differentiable import gini  # noqa: E402
from modelly.zoo.measures import gini as numpy_gini  # noqa: E402

APPROXIMATE = "ignore::modelly.diff.GradientApproximationWarning"
AGENTS = 500


def growth_model():
    """Wealth growing at rate ``g`` plus pathwise noise, and a non-differentiable counter."""

    def init(params, rng):
        return {"w": jnp.ones(AGENTS), "steps": jnp.zeros(()), "frozen": jnp.zeros(())}

    @phase
    def grow(state, params, rng):
        return {"w": state["w"] * (1 + params["g"] + 0.01 * rng.normal((AGENTS,)))}

    @phase(differentiable=False)
    def count(state, params, rng):
        return {"steps": state["steps"] + 1, "frozen": state["w"].mean() * params["g"]}

    outputs = {"mean": lambda s, p: s["w"].mean(), "frozen": lambda s, p: s["frozen"]}
    return DiffModel(init, [grow, count], outputs)


def test_simulate_records_the_initial_state_and_every_step():
    """Outputs have steps + 1 values; the run is the same for the same seed."""
    model = growth_model()
    series = model.simulate({"g": 0.01}, steps=5, seed=3)
    assert series["mean"].shape == (6,) and float(series["mean"][0]) == 1.0
    again = model.simulate({"g": 0.01}, steps=5, seed=3)
    assert np.array_equal(series["mean"], again["mean"])
    assert "grow" in repr(model) and model.phases[1].differentiable is False


def test_pathwise_gradient_agrees_with_finite_differences():
    """A smooth model: jax.grad equals central differences."""
    model = growth_model()
    check = check_gradients(lambda p: model.simulate(p, 10, 1)["mean"][-1], {"g": 0.02})
    assert check.ok, check
    assert check.relative_error["g"] < 1e-6


def test_non_differentiable_phase_stops_the_gradient():
    """An output written by a differentiable=False phase has zero gradient."""
    model = growth_model()
    grad = jax.grad(lambda p: model.simulate(p, 4, 1)["frozen"][-1])({"g": 0.05})
    assert float(grad["g"]) == 0.0


def test_validation():
    """Unknown estimators, empty outputs and phases adding state entries are refused."""
    adds = DiffModel(
        lambda p, r: {"x": jnp.zeros(())},
        [lambda s, p, r: {"y": s["x"]}],
        {"x": lambda s, p: s["x"]},
    )
    with pytest.raises(ValueError, match="declare every state entry"):
        adds.simulate({}, 2)
    with pytest.raises(ValueError):
        DiffModel(lambda p, r: {}, [], {"x": lambda s, p: 0.0}, estimator="magic")
    with pytest.raises(ValueError):
        DiffModel(lambda p, r: {}, [], {})
    with pytest.raises(ValueError):
        DiffRandom(jax.random.key(0)).bernoulli(jnp.full(3, 0.5), estimator="magic")


def test_bernoulli_estimators_warn_and_behave():
    """Every estimator warns; straight-through and score function draw exact 0/1 values."""
    p = jnp.full(10_000, 0.3)
    for estimator in (STRAIGHT_THROUGH, SCORE_FUNCTION):
        with pytest.warns(GradientApproximationWarning):
            draw = DiffRandom(jax.random.key(1), estimator).bernoulli(p)
        assert set(np.unique(np.asarray(draw)).tolist()) == {0.0, 1.0}
        assert abs(float(draw.mean()) - 0.3) < 0.02
    with pytest.warns(GradientApproximationWarning):
        relaxed = DiffRandom(jax.random.key(1), GUMBEL_SOFTMAX).bernoulli(p)
    inside = (relaxed > 0) & (relaxed < 1)
    assert (
        float(relaxed.min()) >= 0
        and float(relaxed.max()) <= 1
        and float(inside.mean()) > 0.5
    )
    exact = DiffRandom(jax.random.key(1), differentiable=False).bernoulli(p)
    assert set(np.unique(np.asarray(exact)).tolist()) == {0.0, 1.0}


@pytest.mark.filterwarnings(APPROXIMATE)
def test_straight_through_gradient_is_the_probability_derivative():
    """D mean(draw) / dp is 1 through straight-through (biased, but in the right direction)."""
    grad = jax.grad(
        lambda q: (
            DiffRandom(jax.random.key(2), STRAIGHT_THROUGH)
            .bernoulli(jnp.full(100, q))
            .mean()
        )
    )(0.4)
    assert abs(float(grad) - 1.0) < 1e-6


@pytest.mark.filterwarnings(APPROXIMATE)
def test_score_function_is_unbiased_on_average():
    """Averaged over seeds, the score-function estimate of d E[mean]/dp is near 1."""

    def surrogate(q, key):
        rng = DiffRandom(key, SCORE_FUNCTION)
        value = rng.bernoulli(jnp.full(50, q)).mean()
        stop = jax.lax.stop_gradient
        return value + stop(value) * (rng.log_prob - stop(rng.log_prob))

    keys = jax.random.split(jax.random.key(3), 4000)
    grads = jax.vmap(jax.grad(surrogate), in_axes=(None, 0))(0.3, keys)
    spread = float(grads.std()) / np.sqrt(len(keys))
    assert abs(float(grads.mean()) - 1.0) < 4 * spread


def test_zoo_gini_matches_the_numpy_measure():
    """The JAX Gini of the zoo twin is the zoo's own Gini."""
    wealth = np.random.default_rng(0).lognormal(size=300)
    assert abs(float(gini(jnp.asarray(wealth))) - numpy_gini(wealth)) < 1e-6


def test_zoo_wealth_gradients_agree_with_finite_differences():
    """Bouchaud-Mezard: exact pathwise gradients of the Gini series, both parameters."""
    model = wealth_model(n=300, dt=0.01)

    def mean_gini(params):
        return model.simulate(params, 60, 4)["gini"].mean()

    check = check_gradients(mean_gini, {"volatility": 1.2, "exchange": 0.8})
    assert check.ok, check
    assert check.autodiff["volatility"] > 0 > check.autodiff["exchange"]


@pytest.mark.filterwarnings(APPROXIMATE)
def test_zoo_bass_relaxed_gradients_agree_with_finite_differences():
    """Bass with Gumbel-softmax: the relaxed model is smooth, so the gradient checks out."""
    model = bass_model(households=400, estimator=GUMBEL_SOFTMAX)

    def final(params):
        return model.simulate(params, 30, 2)["adoption"][-1]

    check = check_gradients(
        final, {"innovation": 0.03, "imitation": 0.4}, tolerance=1e-3
    )
    assert check.ok, check


@pytest.mark.filterwarnings(APPROXIMATE)
def test_straight_through_does_not_pass_a_finite_difference_check():
    """With exact 0/1 draws the output is a step function: the check says so."""
    model = bass_model(households=400)

    def final(params):
        return model.simulate(params, 30, 2)["adoption"][-1]

    check = check_gradients(final, {"innovation": 0.03, "imitation": 0.4})
    assert not check.ok
