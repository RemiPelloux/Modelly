"""The coupling schedule: who reads which quantity, who writes it, and in what order.

A ``Coupling`` runs components (fields, ODEs, stock-flow models and agent phases) once per
step. Each component declares the quantities it ``reads`` and ``writes``; the values live in
the coupling, by name (``coupling["occupied"]``). Components run phase by phase, phase 0
first; within a phase a writer runs before its readers. A component that reads a quantity
written in a later phase sees the value of the previous step, so feedback between agents
and a continuous process is a loop across two phases.

``build`` checks the declarations before the first step and raises ``CouplingError`` for a
quantity read but never written, a quantity with two writers, a cycle of reads and writes
inside one phase (no order would be right), and a quantity read before its writer has run
with no initial value to read.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from difflib import get_close_matches
from typing import Any, Protocol

from modelly.core.exceptions import ModellyException


class CouplingError(ModellyException, ValueError):
    """An inconsistent coupling schedule, or a continuous component that cannot step."""


class Component(Protocol):
    """What a coupling runs: a label, declared reads and writes, ``start`` and ``run``."""

    label: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]

    def start(self, coupling: Coupling) -> None:
        """Publish the initial value of every quantity this component writes, if it has one."""

    def run(self, coupling: Coupling, time: float, duration: float) -> None:
        """Advance from ``time`` to ``time + duration``, reading and writing ``coupling``."""


class Phase:
    """An agent step phase (or any callable) as a coupling component.

    Attributes:
        function: called with no arguments on every step, typically a model method.
        reads: the quantities it reads.
        writes: the quantities it writes.
        initial: initial values of some of its writes, for readers that run before it.
    """

    def __init__(
        self,
        function: Callable[[], Any],
        reads: Iterable[str] = (),
        writes: Iterable[str] = (),
        initial: dict[str, Any] | None = None,
    ) -> None:
        """Wrap ``function``; use a method or a module-level function so it can be saved."""
        self.function = function
        self.label = f"Phase {getattr(function, '__name__', type(function).__name__)!r}"
        self.reads = tuple(reads)
        self.writes = tuple(writes)
        self.initial = dict(initial or {})
        undeclared = sorted(set(self.initial) - set(self.writes))
        if undeclared:
            raise CouplingError(
                f"{self.label} has initial values for {undeclared}, which it does not write."
            )

    def start(self, coupling: Coupling) -> None:
        """Publish the initial values not yet set, so a rebuild keeps the current ones."""
        for name, value in self.initial.items():
            coupling.values.setdefault(name, value)

    def run(self, coupling: Coupling, time: float, duration: float) -> None:
        """Call the function."""
        self.function()


class Coupling:
    """A schedule of components, checked at build time and run once per step.

    Attributes:
        values: the current value of every quantity, by name.
        time: the coupling's time, advanced by ``step``.

    Example:
        >>> def emit():
        ...     coupling["load"] = 2.0
        >>> def absorb(t, y, inputs):
        ...     return inputs["load"] - y
        >>> from modelly.couple.ode import ODE
        >>> coupling = Coupling()
        >>> phase = coupling.add(Phase(emit, writes=["load"]))
        >>> tank = coupling.add(ODE(absorb, {"level": 0.0}, reads=["load"]), phase=1)
        >>> coupling.build().order
        ["Phase 'emit'", "ODE 'absorb'"]
        >>> coupling.step()
        >>> round(coupling["level"], 6)
        1.264241
    """

    def __init__(self) -> None:
        """An empty schedule at time 0."""
        self.values: dict[str, Any] = {}
        self.time = 0.0
        self._entries: list[tuple[int, Component]] = []
        self._order: list[Component] | None = None
        self._running: Component | None = None

    def add[C: Component](self, component: C, phase: int = 0) -> C:
        """Schedule ``component`` in ``phase`` (lower phases run first) and return it."""
        self._entries.append((phase, component))
        self._order = None
        return component

    @property
    def order(self) -> list[str]:
        """The labels of the components in the order they run (after ``build``)."""
        return [component.label for component in self._order or ()]

    def build(self) -> Coupling:
        """Check the declarations, order the components and publish initial values.

        Raises:
            CouplingError: a read with no writer, two writers of one quantity, a cycle in
                one phase, or a read before the first write with no initial value.
        """
        writers = _writers(self._entries)
        _check_reads(self._entries, writers)
        order: list[Component] = []
        for phase in sorted({phase for phase, _ in self._entries}):
            members = [c for p, c in self._entries if p == phase]
            order.extend(_topological(members, writers, phase))
        for component in order:
            component.start(self)
        _check_initial(order, writers, self.values)
        self._order = order
        return self

    def step(self, duration: float = 1.0) -> None:
        """Run every component once, from ``time`` to ``time + duration``."""
        if self._order is None:
            self.build()
        for component in self._order:
            self._running = component
            try:
                component.run(self, self.time, duration)
            finally:
                self._running = None
        self.time += duration

    def __getitem__(self, name: str) -> Any:
        """The current value of quantity ``name``."""
        return self.values[name]

    def __setitem__(self, name: str, value: Any) -> None:
        """Set quantity ``name``; during a step only the running component's writes."""
        running = self._running
        if running is not None and name not in running.writes:
            raise CouplingError(
                f"{running.label} wrote {name!r}, which it does not declare in writes={running.writes}."
            )
        self.values[name] = value


def _writers(entries: list[tuple[int, Component]]) -> dict[str, Component]:
    """The writer of every quantity; two writers of one quantity is an error."""
    writers: dict[str, Component] = {}
    for _, component in entries:
        for name in component.writes:
            other = writers.setdefault(name, component)
            if other is not component:
                raise CouplingError(
                    f"{name!r} has two writers: {other.label} and {component.label}."
                )
    return writers


def _check_reads(
    entries: list[tuple[int, Component]], writers: dict[str, Component]
) -> None:
    """Every quantity read has a writer."""
    for _, component in entries:
        for name in component.reads:
            if name not in writers:
                close = get_close_matches(name, list(writers))
                hint = f" Did you mean {', '.join(map(repr, close))}?" if close else ""
                raise CouplingError(
                    f"{component.label} reads {name!r}, which nobody writes.{hint}"
                )


def _topological(
    members: list[Component], writers: dict[str, Component], phase: int
) -> list[Component]:
    """Order one phase so writers run before their readers; ties keep insertion order."""
    needs = {
        id(c): {
            id(writers[name])
            for name in c.reads
            if writers[name] in members and writers[name] is not c
        }
        for c in members
    }
    done: set[int] = set()
    order: list[Component] = []
    while len(order) < len(members):
        ready = [c for c in members if id(c) not in done and needs[id(c)] <= done]
        if not ready:
            stuck = [c.label for c in members if id(c) not in done]
            raise CouplingError(
                f"Phase {phase} has a cycle of reads and writes between {', '.join(stuck)}; "
                "put one of them in a later phase so it reads the previous step's values."
            )
        order.append(ready[0])
        done.add(id(ready[0]))
    return order


def _check_initial(
    order: list[Component], writers: dict[str, Component], values: dict[str, Any]
) -> None:
    """A quantity read before its writer runs needs an initial value."""
    position = {id(c): i for i, c in enumerate(order)}
    for i, component in enumerate(order):
        for name in component.reads:
            writer = writers[name]
            if position[id(writer)] > i and name not in values:
                raise CouplingError(
                    f"{component.label} reads {name!r} before {writer.label} writes it, "
                    "and there is no initial value: give the writer one."
                )
