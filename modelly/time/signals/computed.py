"""Dependency bookkeeping for computed properties.

These helpers keep a ComputedState's subscriptions in step with the observables
it reads. They hold no tracking state themselves: the currently evaluating
computed lives in ``modelly.time.signals.core``.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from modelly.time.signals.types import ObservableSignals
from modelly.time.signals.util import ALL, SignalType

if TYPE_CHECKING:
    from modelly.time.signals.emitters import HasEmitters

# A dependency spec is (observable_name, *signal_types); one element means ALL.
_NAME_AND_SIGNALS = 2


class ComputedProperty(property):
    """A custom property class to identify computed properties."""

    signal_types = ObservableSignals


class ComputedStateBase:
    """The per-instance data of a computed property; core.ComputedState adds evaluation."""

    __slots__ = [
        "__weakref__",
        "dependencies",
        "func",
        "is_dirty",
        "name",
        "owner",
        "parents",
        "value",
    ]

    def __init__(
        self,
        owner: HasEmitters,
        name: str,
        func: Callable,
        dependencies: Iterable[tuple[str, str | SignalType]] | None = None,
    ):
        """Initialize a ComputedState.

        Args:
            owner: the HasEmitters instance on which this state is defined
            name: the name of the computed property
            func: the computation function
            dependencies: optional iterable of explicit dependencies to track
        """
        self.owner = owner
        self.name = name
        self.func = func
        self.value = None
        self.is_dirty = True
        self.parents: weakref.WeakKeyDictionary[HasEmitters, dict[str, Any]] = (
            weakref.WeakKeyDictionary()
        )
        self.dependencies: list[tuple[str, SignalType]] = []

        if dependencies:
            _subscribe_dependencies(self, owner, dependencies)

    def _set_dirty(self, signal):
        if not self.is_dirty:
            self.is_dirty = True
            self.owner.notify(self.name, ObservableSignals.CHANGED, old=self.value)

    def _record_access(
        self, parent: HasEmitters, name: str, current_value: Any
    ) -> None:
        """Records access to a parent Observable.

        Args:
            parent: the HasEmitters instance to which the Observable belongs
            name: the public name of the Observable
            current_value: the current value of the Observable

        """
        try:
            self.parents[parent][name] = current_value
        except KeyError:
            self.parents[parent] = {name: current_value}


def _subscribe_dependencies(
    state: ComputedStateBase,
    owner: HasEmitters,
    dependencies: Iterable[tuple[str, str | SignalType]],
) -> None:
    """Subscribe state to the explicitly declared dependencies on owner."""
    for dep_spec in dependencies:
        if isinstance(dep_spec, tuple) and len(dep_spec) >= _NAME_AND_SIGNALS:
            obs_name = dep_spec[0]
            signal_types = dep_spec[1:]
            for signal_type in signal_types:
                owner.observe(obs_name, signal_type, state._set_dirty)
                state.dependencies.append((obs_name, signal_type))
        elif isinstance(dep_spec, tuple) and len(dep_spec) == 1:
            obs_name = dep_spec[0]
            owner.observe(obs_name, ALL, state._set_dirty)
            state.dependencies.append((obs_name, ALL))


def _resubscribe(state: ComputedStateBase, old_parents: Any) -> None:
    """Diffing engine: subscribe/unsubscribe as dependencies come and go."""
    old_deps = {(p, attr) for p, attrs in old_parents.items() for attr in attrs}
    new_deps = {(p, attr) for p, attrs in state.parents.items() for attr in attrs}

    for p, attr in old_deps - new_deps:
        p.unobserve(attr, ALL, state._set_dirty)
    for p, attr in new_deps - old_deps:
        p.observe(attr, ALL, state._set_dirty)


def _parents_changed(parents: Any) -> bool:
    """Return whether any recorded parent value differs from its current value."""
    if not parents:
        return True
    for parent, observations in parents.items():
        if parent is None:
            return True
        for attr, old_val in observations.items():
            current_val = getattr(parent, attr)
            if current_val != old_val:
                return True
    return False
