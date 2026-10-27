"""Check that a split run gives what one process gives, byte for byte.

``single_process`` runs the model as anyone would, ``model.step()`` after
``model.step()`` in one process, and records its reporters and the full state
of every agent. ``check_independence`` runs the same scenario split by each
partition given, on the ``local`` backend, and raises at the first reporter
value or agent state that differs, naming it. The partition-independence test
suite is this check on reference models; run it on your own model before a
long split run, since it catches what the build checks cannot see (a phase
that reads past its radius, depends on the order of neighbours, or writes to
another agent).
"""

from __future__ import annotations

import pickle
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from modelly.distributed.cluster import TIME, Cluster
from modelly.distributed.contract import PartitionError, plan_of
from modelly.distributed.reduce import states

PROTOCOL = pickle.HIGHEST_PROTOCOL


@dataclass
class Run:
    """The outputs of a run: reporter rows and the state of every agent."""

    rows: pd.DataFrame
    states: list[tuple]


def single_process(model_class: type, scenario: Any, steps: int) -> Run:
    """Run ``model_class`` in one process for ``steps`` steps from a copy of ``scenario``."""
    plan = plan_of(model_class)
    model = model_class(scenario=pickle.loads(pickle.dumps(scenario, PROTOCOL)))  # noqa: S301
    rows = [{TIME: float(model.time), **plan.report(model)}]
    for _ in range(int(steps)):
        model.step()
        rows.append({TIME: float(model.time), **plan.report(model)})
    return Run(pd.DataFrame(rows), sorted(states(model.agents)))


def split_run(model_class: type, scenario: Any, partition: Any, steps: int) -> Run:
    """Run ``model_class`` split by ``partition`` on the local backend."""
    with Cluster("local") as cluster:
        model = cluster.build(model_class, scenario, partition)
        model.run_for(steps)
        return Run(model.collect(), model.states())


def first_difference(reference: Run, other: Run) -> str | None:
    """A description of the first output that differs, or ``None``."""
    if not reference.rows.equals(other.rows):
        for (i, left), (_, right) in zip(
            reference.rows.iterrows(), other.rows.iterrows(), strict=False
        ):
            if not left.equals(right):
                return f"reporters at row {i}: {left.to_dict()} != {right.to_dict()}"
        return f"{len(reference.rows)} rows != {len(other.rows)} rows"
    keys = [row[0] for row in reference.states]
    if keys != [row[0] for row in other.states]:
        return "the two runs end with different agents"
    for left, right in zip(reference.states, other.states, strict=True):
        if left != right:
            return (
                f"agent {left[0]}: state or location differs ({left[1]} vs {right[1]})"
            )
    return None


def check_independence(
    model_class: type, scenario: Any, partitions: Sequence[Any], steps: int
) -> Run:
    """Run one process and every split in ``partitions``; raise if any output differs.

    Returns:
        The single-process run.

    Raises:
        PartitionError: naming the partition and the first differing output.
    """
    reference = single_process(model_class, scenario, steps)
    for partition in partitions:
        difference = first_difference(
            reference, split_run(model_class, scenario, partition, steps)
        )
        if difference is not None:
            raise PartitionError(
                f"{model_class.__name__} split by {partition} differs from one "
                f"process: {difference}"
            )
    return reference
