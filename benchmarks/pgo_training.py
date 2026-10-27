"""The training run of the profile-guided build of ``benchmarks/pgo.py``.

    python benchmarks/pgo_training.py

Runs, in this interpreter, every Modelly variant of every playbook at its
``small`` size, the 17 core operations of the performance guard
(``benchmarks/micro/ops.py``) and an event-heavy schedule, so the instrumented
compiled modules record the branches and calls a real model takes. Its output
is the profile the compiler reads back; it prints nothing else.
"""

from __future__ import annotations

import importlib
import random
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
OP_CALLS = 200  # calls of each core operation
EVENTS = 20_000  # one-off events scheduled at random delays
PATCHES = 2_000


def playbooks() -> None:
    """Each Modelly playbook variant, small size, its full number of steps."""
    sys.path.insert(0, str(HERE / "playbooks"))
    registry = importlib.import_module("registry")
    for name, spec in registry.PLAYBOOKS.items():
        params = {**spec["params"], **spec["sizes"]["small"]}
        for variant, module_name in spec["variants"].items():
            if variant.startswith("modelly"):
                module = importlib.import_module(f"{name}.{module_name}")
                module.simulate(module.build(seed=1, **params), spec["steps"])


def core_operations() -> None:
    """The performance guard's operations, each called OP_CALLS times."""
    sys.path.insert(0, str(HERE / "micro"))
    ops = importlib.import_module("ops")
    for function, _ in ops.operations().values():
        for _ in range(OP_CALLS):
            function()


class Patch:
    """A regrowing patch: one event per regrowth."""

    def regrow(self) -> None:
        """Regrow, and schedule nothing: the schedule is driven from outside."""


def events() -> None:
    """Events at random delays, with ties, cancellations and numpy times."""
    from modelly import Model  # noqa: PLC0415 - after the path setup

    model, draw = Model(rng=1), random.Random(1)
    patches = [Patch() for _ in range(PATCHES)]
    for i in range(EVENTS):
        event = model.schedule_event(
            draw.choice(patches).regrow, after=draw.randrange(1, 40) / (1 + i % 3)
        )
        if i % 11 == 0:
            event.cancel()
        if i % 100 == 0:
            model.step()
    model.run_for(50)


def main() -> int:
    """Run the three workloads."""
    warnings.simplefilter("ignore")
    playbooks()
    core_operations()
    events()
    return 0


if __name__ == "__main__":
    sys.exit(main())
