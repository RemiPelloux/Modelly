"""The result of :func:`modelly.timetravel.diff`: where two runs diverge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Difference:
    """One value that differs between two runs.

    Attributes:
        step: The model time at which the value differs.
        name: The reporter, model attribute or agent attribute that differs.
        a: Its value in the first run.
        b: Its value in the second run.
        agent: The ``unique_id`` of the agent, or None for a model value.
        agent_class: The class name of the agent, when known.
    """

    step: float
    name: str
    a: Any
    b: Any
    agent: int | None = None
    agent_class: str | None = None

    def __str__(self) -> str:
        """One line: step, who, what, both values."""
        if self.agent is None:
            who = "model"
        elif self.agent_class is None:
            who = f"agent {self.agent}"
        else:
            who = f"agent {self.agent} ({self.agent_class})"
        return f"step {self.step:g}, {who}, {self.name}: {self.a!r} != {self.b!r}"


@dataclass(frozen=True)
class RunDiff:
    """Where two runs first diverge, in their collected data and their state.

    Attributes:
        data: The first difference in the collected data (model reporters,
            then agent reporters), or None.
        state: The first difference in model or agent state, or None. For two
            recorders it is at the first step where the states differ; for
            two models, at their current time.
    """

    data: Difference | None = None
    state: Difference | None = None

    @property
    def identical(self) -> bool:
        """Whether no difference was found."""
        return self.data is None and self.state is None

    @property
    def step(self) -> float | None:
        """The first step at which the runs differ, or None."""
        found = [d.step for d in (self.data, self.state) if d is not None]
        return min(found, default=None)

    def report(self) -> str:
        """A readable report of the divergence."""
        if self.identical:
            return "The runs are identical."
        lines = [f"The runs diverge at step {self.step:g}."]
        if self.data is not None:
            lines.append(f"Collected data: {self.data}")
        if self.state is not None:
            lines.append(f"State: {self.state}")
        return "\n".join(lines)

    def __str__(self) -> str:
        """The readable report."""
        return self.report()
