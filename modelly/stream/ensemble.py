"""Ensembles: replicates of one scenario advanced in lock step.

An :class:`Ensemble` builds ``n`` models from one scenario, each with a seed
spawned from the scenario's seed sequence, so replicate ``i`` gets the seed
``Scenario.spawn_replications(n)[i]`` gets on a fresh scenario::

    ensemble = Ensemble(Epidemic, EpidemicScenario(rng=7), 40)
    ensemble.advance(10)                      # every replicate to time 10
    ensemble.band(observe)                    # quantiles across replicates, a DataFrame

Replicates run one after the other in this process, in index order: the
ensemble is deterministic for a seed. The assimilation filters
(:mod:`modelly.stream.particle`, :mod:`modelly.stream.kalman`) work on an
ensemble: they weight, duplicate and adjust its replicates between advances.

Every random draw the ensemble or a filter makes outside the models comes from
a seed sequence derived from the scenario's with a domain of its own
(``derived_seed``), so no derived stream equals a replicate's or an agent's.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING

import numpy as np

from modelly.core.checkpoint import checkpoint_bytes, model_from_bytes
from modelly.stream.bands import (
    DEFAULT_QUANTILES,
    _band_frame,
    _band_rows,
    forecast_band,
)
from modelly.timetravel.recorder import reseed_model

if TYPE_CHECKING:
    import pandas as pd

    from modelly.core.model import Model
    from modelly.scenarios import Scenario
    from modelly.stream.operators import ObservationOperator

MIN_REPLICATES = 2
# Domains of the derived seed sequences, as ASCII: "PRIO", "RSMP", "ENKF".
PRIOR_DOMAIN = 0x5052494F
RESAMPLE_DOMAIN = 0x52534D50
KALMAN_DOMAIN = 0x454E4B46

Prior = Mapping[str, Callable[[np.random.Generator], float]]


def derived_seed(
    root: np.random.SeedSequence, domain: int, *key: int
) -> np.random.SeedSequence:
    """The seed sequence of ``key`` in ``domain``, below ``root``.

    ``SeedSequence.spawn`` hands out keys ``(*root.spawn_key, i)``; these keys
    are one level deeper and start with ``domain``, a number far above any
    replicate count, so they never collide with a spawned seed.
    """
    return np.random.SeedSequence(
        root.entropy, spawn_key=(*root.spawn_key, domain, *key)
    )


def replicate_scenarios(scenario: Scenario, n: int) -> list[Scenario]:
    """``n`` replicates of ``scenario``, as ``spawn_replications(n)`` on a fresh one.

    The scenario's seed sequence is left as it was, so building a second
    ensemble from the same scenario gives the same replicates.
    """
    root = scenario.seed_sequence
    return [
        type(scenario)(
            rng=np.random.SeedSequence(root.entropy, spawn_key=(*root.spawn_key, i)),
            scenario_id=scenario.scenario_id,
            replication_id=i,
            **dict(scenario),
        )
        for i in range(n)
    ]


class Ensemble:
    """``n`` replicates of a model, built from one scenario with spawned seeds."""

    def __init__(
        self,
        factory: Callable[..., Model],
        scenario: Scenario,
        n: int,
        *,
        prior: Prior | None = None,
    ) -> None:
        """Build ``factory(scenario=replicate)`` for each of ``n`` replicate scenarios.

        A model class is a factory. ``prior`` maps a model attribute to a
        callable drawing its starting value from a numpy generator: each
        replicate gets its own draw, set after the model is built and before
        it runs, from a generator derived from the scenario's seed.
        """
        if n < MIN_REPLICATES:
            raise ValueError(
                f"an ensemble needs at least {MIN_REPLICATES} replicates, got {n}"
            )
        self.scenario = scenario
        self.models: list[Model] = [
            factory(scenario=child) for child in replicate_scenarios(scenario, n)
        ]
        if prior:
            self._draw_prior(prior)

    def _draw_prior(self, prior: Prior) -> None:
        """Set each prior attribute on every replicate, replicate by replicate."""
        rng = np.random.default_rng(self.seed(PRIOR_DOMAIN))
        for model in self.models:
            for name, draw in prior.items():
                setattr(model, name, float(draw(rng)))

    def seed(self, domain: int, *key: int) -> np.random.SeedSequence:
        """A seed sequence derived from the scenario's (see ``derived_seed``)."""
        return derived_seed(self.scenario.seed_sequence, domain, *key)

    def __len__(self) -> int:
        """The number of replicates."""
        return len(self.models)

    def __iter__(self) -> Iterator[Model]:
        """The replicates, in index order."""
        return iter(self.models)

    def __getitem__(self, index: int) -> Model:
        """Replicate ``index``."""
        return self.models[index]

    @property
    def time(self) -> float:
        """The time every replicate has reached."""
        return self.models[0].time

    def advance(self, until: float) -> None:
        """Run every replicate to time ``until``, one after the other.

        Nothing happens when the replicates are already at ``until``.

        Raises:
            ValueError: If ``until`` is before the current time.
        """
        if until < self.time:
            raise ValueError(
                f"cannot advance to {until}: the ensemble is at time {self.time}"
            )
        if until == self.time:
            return
        for model in self.models:
            model.run_until(until)

    def values(self, operator: ObservationOperator) -> np.ndarray:
        """``operator`` read from every replicate: one row per replicate, one column per quantity."""
        return np.array(
            [list(operator(model).values()) for model in self.models], dtype=float
        )

    def resample(
        self,
        indices: Sequence[int],
        reseed: Callable[[int], np.random.SeedSequence],
    ) -> None:
        """Replace the replicates by ``models[i] for i in indices``, copying duplicates.

        The first slot that takes a replicate keeps the model itself; every
        other slot gets a checkpoint copy (:func:`modelly.core.checkpoint.checkpoint_bytes`)
        reseeded in place from ``reseed(slot)``, so duplicates diverge from
        their next draw on. A copy is a full checkpoint, so it holds every
        agent, space, column and scheduled event of the original.

        Note:
            Per-agent streams (``agent_streams = True``) are copied, not
            reseeded: only ``model.random`` and ``model.rng`` are.
        """
        if len(indices) != len(self.models):
            raise ValueError(
                f"resample needs {len(self.models)} indices, got {len(indices)}"
            )
        kept: set[int] = set()
        frozen: dict[int, bytes] = {}
        replicates = []
        for slot, source in enumerate(int(i) for i in indices):
            if source not in kept:
                kept.add(source)
                replicates.append(self.models[source])
                continue
            if source not in frozen:
                frozen[source] = checkpoint_bytes(self.models[source])
            copy = model_from_bytes(frozen[source], f"replicate {source}")
            reseed_model(copy, reseed(slot))
            replicates.append(copy)
        self.models = replicates

    def band(
        self,
        operator: ObservationOperator,
        quantiles: Sequence[float] = DEFAULT_QUANTILES,
        weights: Sequence[float] | None = None,
    ) -> pd.DataFrame:
        """Mean and quantiles of ``operator`` across replicates, at the current time.

        One row per quantity, with columns ``time``, ``quantity``, ``mean`` and
        one ``q<level>`` per quantile (``q0.05``, ``q0.5``, ...): plain data for
        a plot or a live view. ``weights`` weight the replicates (equal by default).
        """
        rows = _band_rows(
            self.time, operator.names, self.values(operator), weights, quantiles
        )
        return _band_frame(rows, quantiles)

    def forecast(
        self,
        operator: ObservationOperator,
        until: float,
        *,
        every: float = 1.0,
        quantiles: Sequence[float] = DEFAULT_QUANTILES,
        weights: Sequence[float] | None = None,
    ) -> pd.DataFrame:
        """The band of ``operator`` from now to ``until``, every ``every`` time units.

        The forecast runs checkpoint copies of the replicates: the ensemble
        itself stays where it is. The frame has the columns of ``band``, one
        row per time and quantity, the current time first.
        """
        return forecast_band(
            self.models,
            operator,
            until,
            every=every,
            quantiles=quantiles,
            weights=weights,
        )
