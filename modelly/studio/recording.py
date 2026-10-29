"""A Studio session as a Python script that rebuilds its live run.

Studio records what makes the live run what it is: each new run (the panel's values and the
seed it was built with) and each replay from a scrubbed-to step (the Scenario values changed
and, when it changed, the seed). Steps are counted from the model's time, which every step
advances by one. Scrubbing alone leaves the live run as it was, so it is not recorded; a
replay cuts the steps after the step it starts from.

``SessionRecording.script(time)`` writes the record as a plain Python script: it builds the
model as Studio did, steps it, applies each replay's changes at its step, and ends with the
model in the state the live run had at ``time``. Checkpoints restore a run bit for bit, so
replaying from a step and stepping on to it give the same state, and the script needs no
checkpoint file.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

NEW_RUN, REPLAY = "new run", "replay"
INDENT = "    "

HEADER = '''"""Rebuild a Modelly Studio session: the live run of {name} when it was saved.

Run it with ``python {filename}``; ``replay()`` returns the model at step {time:g}, in the
state Studio showed. Saved by Modelly Studio.
"""

import importlib

import numpy as np

from modelly.profile.loader import build_model
from modelly.studio.loader import load_model_class
from modelly.timetravel.recorder import reseed_model, thaw

TARGET = {target!r}


def replay():
    """The model in the state the Studio session's live run ended in."""
    model_class = load_model_class(TARGET)
'''

FOOTER = """    return model


if __name__ == "__main__":
    import sys

    model = replay()
    sys.stdout.write(f"{type(model).__name__} at step {model.time:g}\\n")
"""


@dataclass
class Segment:
    """One stretch of the live run: how it began and the time it began at.

    Attributes:
        kind: ``new run`` (the model was built) or ``replay`` (a scrubbed-to state with
            changed values became the live run).
        values: For a new run, every value the model was built with; for a replay, the
            Scenario values it changed.
        seed: The seed a new run was built with, or the seed a replay reseeded with
            (None when a replay kept the generators as they were).
        start: The model's time when the stretch began.
        steps: The steps taken in it, set when a later replay cuts it short.
    """

    kind: str
    values: dict[str, Any]
    seed: int | None
    start: float = 0.0
    steps: int | None = field(default=None)


def literal(value: Any) -> str:
    """``value`` as Python source: a literal, or an Enum member looked up by name."""
    if isinstance(value, enum.Enum):
        owner = type(value)
        return (
            f"importlib.import_module({owner.__module__!r})"
            f".{owner.__qualname__}[{value.name!r}]"
        )
    return repr(value)


def _mapping(values: dict[str, Any]) -> str:
    """A dict display of ``values`` in source form, keys in panel order."""
    items = ", ".join(f"{name!r}: {literal(value)}" for name, value in values.items())
    return "{" + items + "}"


def _steps(count: int) -> list[str]:
    """Source lines that take ``count`` steps, as Studio does: one ``step()`` at a time."""
    if count <= 0:
        return []
    return [f"for _ in range({count}):", f"{INDENT}model.step()"]


def _segment_lines(segment: Segment, steps: int) -> list[str]:
    """Source lines for one segment followed by its ``steps`` steps."""
    if segment.kind == NEW_RUN:
        lines = [
            f"# a new run, seed {segment.seed}",
            f"model = build_model(model_class, {_mapping(segment.values)}, {segment.seed!r})",
        ]
    else:
        # A restored state's scenario can be changed (see the time travel guide).
        lines = [f"# replayed from step {segment.start:g}", "thaw(model)"]
        lines += [
            f"model.scenario.{name} = {literal(value)}"
            for name, value in segment.values.items()
        ]
        if segment.seed is not None:
            lines.append(f"reseed_model(model, np.random.SeedSequence({segment.seed}))")
    return lines + _steps(steps)


class SessionRecording:
    """What a Studio session did to its live run, and the script that does it again.

    Args:
        target: The ``path/to/model.py:Class`` or ``module:Class`` Studio was started on.
    """

    def __init__(self, target: str) -> None:
        """Start an empty record for ``target``."""
        self.target = target
        self.segments: list[Segment] = []

    def new_run(self, values: dict[str, Any], seed: int, time: float = 0.0) -> None:
        """A model built with ``values`` and ``seed`` became the live run."""
        self.segments = [Segment(NEW_RUN, dict(values), seed, start=time)]

    def replayed(self, time: float, changes: dict[str, Any], seed: int | None) -> None:
        """The state at ``time`` became the live run, with ``changes`` and ``seed`` applied."""
        last = self.segments[-1]
        last.steps = round(time - last.start)
        self.segments.append(Segment(REPLAY, dict(changes), seed, start=time))

    @property
    def straight(self) -> bool:
        """Whether the live run is one new run stepped on, with no replay in it."""
        return len(self.segments) == 1

    def body(self, time: float) -> list[str]:
        """The source lines of ``replay()``'s body, for a live run now at ``time``."""
        lines = []
        for index, segment in enumerate(self.segments):
            last = index == len(self.segments) - 1
            steps = round(time - segment.start) if last else segment.steps
            lines += _segment_lines(segment, steps)
        return lines

    def script(
        self, time: float, name: str = "the model", filename: str = "session.py"
    ) -> str:
        """The Python script that rebuilds the live run, now at ``time``.

        Raises:
            ValueError: When nothing was recorded yet.
        """
        if not self.segments:
            raise ValueError("nothing recorded: the session has no run yet")
        head = HEADER.format(
            name=name, filename=filename, time=time, target=self.target
        )
        body = "".join(f"{INDENT}{line}\n" for line in self.body(time))
        return head + body + FOOTER


__all__ = ["Segment", "SessionRecording", "literal"]
