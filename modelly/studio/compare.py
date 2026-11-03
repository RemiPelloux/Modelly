"""Comparing scenarios in Studio, without code: the session's model, several parameter sets.

``compare_scenarios(session, scenarios, output)`` runs each scenario (a name and the
parameters it changes from the panel's values) ``replicates`` times on common random
numbers, with ``modelly.decide.compare``, and reads ``output``, a model reporter, at the end
of each run. The Compare tab shows the ranking with intervals and each scenario's paired
difference from the first.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from modelly.decide.compare import Comparison, Strategy, compare
from modelly.profile.loader import build_model

if TYPE_CHECKING:
    from modelly.studio.session import StudioSession

DEFAULT_REPLICATES, DEFAULT_STEPS = 10, 50


def reporters(session: StudioSession) -> list[str]:
    """The model reporters of the session's model, the outputs a comparison can read."""
    collector = getattr(session.model, "datacollector", None)
    return list(getattr(collector, "model_reporters", {}) or {})


def final_value(model: Any, output: str) -> float:
    """The last collected value of the model reporter ``output``."""
    frame = model.datacollector.get_model_vars_dataframe()
    return float(frame[output].iloc[-1])


def compare_scenarios(
    session: StudioSession, scenarios: Mapping[str, Mapping[str, Any]], output: str, *,
    steps: int = DEFAULT_STEPS, replicates: int = DEFAULT_REPLICATES, seed: int | None = None,
) -> Comparison:  # fmt: skip
    """Each scenario's ``output`` after ``steps`` steps, ``replicates`` times, paired.

    Raises:
        ValueError: for an output that is not a model reporter, or fewer than two scenarios.
    """
    if output not in reporters(session):
        raise ValueError(
            f"{output!r} is not a model reporter: one of {reporters(session)}"
        )
    if len(scenarios) < 2:
        raise ValueError("a comparison needs at least two scenarios")
    base = dict(session.values)

    def run(params: Mapping[str, Any], run_seed: int) -> dict[str, float]:
        model = build_model(session.model_class, {**base, **params}, run_seed)
        model.run_for(int(steps))
        return {output: final_value(model, output)}

    strategies = [Strategy(name, dict(changes)) for name, changes in scenarios.items()]
    start = session.seed if seed is None else seed
    return compare(run, strategies, replicates=int(replicates), seed=int(start))
