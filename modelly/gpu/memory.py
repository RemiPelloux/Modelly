"""Populations larger than the GPU's memory: plan batches and run a phase over them.

The columns stay on the host (numpy, or memory-mapped files); a phase runs on
the device one batch of rows at a time. :func:`plan_memory` sizes the batches
from the bytes a row needs on the device (its columns plus the temporaries the
phase makes) and the device's free memory; :func:`run_batched` copies each
batch in, runs the phase and copies its outputs back::

    plan = plan_memory(len(state), bytes_per_row=64, backend=backend)
    draw = stream.draws()                       # one draw for the whole phase

    def recover(batch, start):
        u = draw.random(len(batch["days"]), start=start)
        return {"state": xp.where(u < gamma, R, batch["state"])}

    out = run_batched(plan, recover, {"state": state, "days": days}, backend)

A phase that draws by position (``start``) gives the same numbers whatever the
batch size, so a batched run equals the run in one batch, bit for bit. Only
phases whose rows do not read each other batch exactly; a reduction over
rows (counts per cell) is a sum of per-batch reductions, which the caller adds.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from modelly.gpu.backend import Backend, get_backend

DEFAULT_FRACTION = (
    0.5  # of the free device memory, leaving room for the pool and others
)
MIN_BATCH_ROWS = 1

Phase = Callable[[dict[str, Any], int], Mapping[str, Any]]


@dataclass(frozen=True)
class MemoryPlan:
    """How many rows go to the device at once.

    Attributes:
        rows: rows of the population.
        batch_rows: rows per batch (the last batch may be shorter).
        bytes_per_row: device bytes one row needs during the phase.
        budget: device bytes the plan allows.
    """

    rows: int
    batch_rows: int
    bytes_per_row: int
    budget: int

    @property
    def batches(self) -> int:
        """The number of batches."""
        return max(1, -(-self.rows // self.batch_rows))

    def slices(self) -> Iterator[slice]:
        """The row range of each batch, in order."""
        for start in range(0, max(self.rows, 1), self.batch_rows):
            yield slice(start, min(start + self.batch_rows, self.rows))


def plan_memory(
    rows: int, bytes_per_row: int, backend: Any = None, budget: int | None = None
) -> MemoryPlan:
    """Batches of rows that fit in ``budget`` bytes (half the free device memory by default).

    Raises:
        ValueError: when ``bytes_per_row`` is not positive.
    """
    if bytes_per_row <= 0:
        raise ValueError("bytes_per_row must be positive")
    if budget is None:
        budget = int(get_backend(backend).free_bytes() * DEFAULT_FRACTION)
    batch_rows = max(MIN_BATCH_ROWS, min(max(rows, 1), budget // bytes_per_row))
    return MemoryPlan(rows, batch_rows, bytes_per_row, budget)


def run_batched(
    plan: MemoryPlan,
    phase: Phase,
    columns: Mapping[str, np.ndarray],
    backend: Backend | str | None = None,
) -> dict[str, np.ndarray]:
    """Run ``phase(batch, start)`` over the batches of ``plan``; host outputs, joined.

    ``batch`` maps each column name to the batch's rows on the device, and
    ``start`` is the batch's first row, for drawing by position. The phase
    returns device arrays, one value per row of the batch.
    """
    backend = get_backend(backend)
    outputs: dict[str, list[np.ndarray]] = {}
    for rows in plan.slices():
        batch = {
            name: backend.asarray(values[rows]) for name, values in columns.items()
        }
        for name, values in phase(batch, rows.start).items():
            outputs.setdefault(name, []).append(backend.to_numpy(values))
    return {name: np.concatenate(parts) for name, parts in outputs.items()}
