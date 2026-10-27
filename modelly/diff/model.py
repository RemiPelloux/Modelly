"""A model as JAX column phases: traced, compiled and differentiated with respect to parameters.

A :class:`DiffModel` is the array side of a Modelly model written with
columns: a state (a dict of column arrays and model-level values), an
``init(params, rng)`` that builds it, and step phases that each return the
columns they change. JAX traces the phases once, runs the steps with
``lax.scan`` and differentiates the recorded outputs with respect to
``params``::

    @phase
    def returns(state, params, rng):
        w = state["wealth"] * jnp.exp(params["volatility"] * rng.normal(n))
        return {"wealth": w / w.mean()}

    @phase(differentiable=False)
    def census(state, params, rng):
        return {"rich": (state["wealth"] > 2).sum()}

    model = DiffModel(init, [returns, census], outputs={"gini": gini})
    series = model.simulate({"volatility": 0.4}, steps=100, seed=1)
    grads = jax.grad(lambda p: model.simulate(p, 100, 1)["gini"][-1])(params)

``differentiable=False`` stops gradients at the phase's updates (bookkeeping,
integer counters, a rule the gradient should not see) and makes its Bernoulli
draws exact 0/1 draws. In a differentiable phase a Bernoulli draw goes through
an estimator (``modelly.diff.estimators``), and warns that the gradient is an
approximation; normal and uniform draws are pathwise and exact.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from modelly.diff._jax import jax, jnp
from modelly.diff.estimators import ESTIMATORS, STRAIGHT_THROUGH, DiffRandom

State = dict[str, Any]
PhaseFunction = Callable[[State, Mapping[str, Any], DiffRandom], Mapping[str, Any]]


@dataclass(frozen=True)
class Phase:
    """One step phase: a function of (state, params, rng) returning updated entries.

    Attributes:
        function: the phase; it returns a dict of the state entries it changes.
        differentiable: whether gradients flow through its updates.
        name: the phase's name (the function's by default).
    """

    function: PhaseFunction
    differentiable: bool = True
    name: str = ""

    def __call__(self, state: State, params: Mapping[str, Any], rng: DiffRandom) -> Any:
        """Run the phase."""
        return self.function(state, params, rng)


def phase(function: PhaseFunction | None = None, *, differentiable: bool = True) -> Any:
    """Declare a step phase, as ``@phase`` or ``@phase(differentiable=False)``."""

    def wrap(fn: PhaseFunction) -> Phase:
        return Phase(fn, differentiable, getattr(fn, "__name__", "phase"))

    return wrap if function is None else wrap(function)


def _check_entries(one: Phase, update: Mapping[str, Any], state: State) -> None:
    """A phase may change the state's entries but not add new ones (scan needs one shape)."""
    added = sorted(set(update) - set(state))
    if added:
        raise ValueError(
            f"phase {one.name!r} returns {added}, which init does not create; "
            "declare every state entry in init"
        )


@dataclass(frozen=True)
class Trace:
    """One simulated run: the output series and the score-function log-probability.

    Attributes:
        outputs: ``{name: array}``, one value per step, the initial state first.
        log_prob: sum of log P(draw) over score-function draws (0 without any).
    """

    outputs: dict[str, Any]
    log_prob: Any


class DiffModel:
    """Column phases over a state of arrays, simulated and differentiated by JAX.

    Args:
        init: ``init(params, rng) -> state``, the initial state (a dict of arrays).
        phases: the step phases in order (``Phase`` objects or plain functions).
        outputs: ``{name: fn(state, params) -> scalar}``, recorded every step.
        estimator: the default estimator of Bernoulli draws (see ``estimators``).
    """

    def __init__(
        self,
        init: Callable[[Mapping[str, Any], DiffRandom], State],
        phases: Sequence[Phase | PhaseFunction],
        outputs: Mapping[str, Callable[[State, Mapping[str, Any]], Any]],
        estimator: str = STRAIGHT_THROUGH,
    ) -> None:
        """Check the phases and the estimator; nothing is traced yet."""
        if estimator not in ESTIMATORS:
            raise ValueError(
                f"estimator must be one of {ESTIMATORS}, not {estimator!r}"
            )
        if not outputs:
            raise ValueError("a DiffModel needs at least one output")
        self.init = init
        self.phases = [p if isinstance(p, Phase) else phase(p) for p in phases]
        self.outputs = dict(outputs)
        self.estimator = estimator

    def record(self, state: State, params: Mapping[str, Any]) -> dict[str, Any]:
        """The outputs of ``state``."""
        return {
            name: jnp.asarray(fn(state, params)) for name, fn in self.outputs.items()
        }

    def _step(self, params: Mapping[str, Any]) -> Callable:
        """The scan body: every phase in order, then the outputs."""

        def body(carry: tuple[State, Any], key: Any) -> tuple:
            state, log_prob = carry
            for one, phase_key in zip(
                self.phases, jax.random.split(key, len(self.phases))
            ):
                rng = DiffRandom(phase_key, self.estimator, one.differentiable)
                update = dict(one(state, params, rng))
                _check_entries(one, update, state)
                if not one.differentiable:
                    update = jax.tree.map(jax.lax.stop_gradient, update)
                state = {**state, **update}
                log_prob = log_prob + rng.log_prob
            return (state, log_prob), self.record(state, params)

        return body

    def trace(self, params: Mapping[str, Any], steps: int, key: Any) -> Trace:
        """Simulate ``steps`` steps from ``key`` (traceable: use it inside jax.grad)."""
        init_key, run_key = jax.random.split(key)
        state = dict(self.init(params, DiffRandom(init_key, self.estimator, False)))
        first = self.record(state, params)
        carry = (state, jnp.zeros(()))
        (_, log_prob), series = jax.lax.scan(
            self._step(params), carry, jax.random.split(run_key, steps)
        )
        outputs = {
            name: jnp.concatenate([first[name][None], series[name]]) for name in first
        }
        return Trace(outputs, log_prob)

    def simulate(self, params: Mapping[str, Any], steps: int, seed: int = 0) -> dict:
        """The output series of one run seeded with ``seed`` (JAX arrays)."""
        return self.trace(params, steps, jax.random.key(seed)).outputs

    def __repr__(self) -> str:
        """Phases and outputs."""
        names = [p.name for p in self.phases]
        return f"<DiffModel phases={names} outputs={list(self.outputs)}>"
