"""Core implementation of Modelly's reactive programming system.

This module provides the foundational classes for Modelly's observable/reactive programming
functionality:

- BaseObservable: Abstract base class defining the interface for all observables
- Observable: Main class for creating observable properties that emit change signals
- computed_property: Decorator for creating properties that automatically update based on dependencies
- HasEmitters: Mixin class that enables an object to contain and manage observables
- emit: Decorator for methods that emit signals

The module implements a robust reactive system where changes to observable properties
automatically trigger updates to dependent computed values and notify subscribed
observers. This enables building models with complex interdependencies while maintaining
clean separation of concerns.

It also owns the dependency-tracking state (CURRENT_COMPUTED, PROCESSING_SIGNALS),
so everything that reads or rebinds that state is defined here.
"""

from __future__ import annotations

import functools
import weakref
from collections import namedtuple
from collections.abc import Callable, Iterable, MutableSequence
from typing import Any

from modelly.time.signals.computed import (
    ComputedProperty,
    ComputedStateBase,
    _parents_changed,
    _resubscribe,
)

# descriptor_generator, ObservableName, SignalSpec, ALL, Message and create_weakref
# are re-exported: they were importable from this module before it was split.
from modelly.time.signals.emitters import (  # noqa: F401
    HasEmitters,
    descriptor_generator,
    emit,
)
from modelly.time.signals.subscriptions import ObservableName, SignalSpec  # noqa: F401
from modelly.time.signals.types import ObservableSignals
from modelly.time.signals.util import (  # noqa: F401
    ALL,
    Message,
    SignalType,
    create_weakref,
)

__all__ = [
    "BaseObservable",
    "HasEmitters",
    "Observable",
    "computed_property",
    "emit",
]

_hashable_signal = namedtuple("_HashableSignal", "instance name")

CURRENT_COMPUTED: ComputedState | None = None  # the current Computed that is evaluating
PROCESSING_SIGNALS: set[_hashable_signal] = set()


class BaseObservable:
    """Base class for all Observables."""

    signal_types: type[SignalType] = SignalType

    def __init__(self, fallback_value=None):
        """Initialize a BaseObservable."""
        super().__init__()
        self.public_name: str
        self.private_name: str
        self.fallback_value = fallback_value

    def __get__(self, instance: HasEmitters, owner):  # noqa: D105
        # Class-level access (e.g. ``MyAgent.value``) returns the descriptor
        # itself, following the standard descriptor protocol used by ``property``.
        if instance is None:
            return self

        value = getattr(instance, self.private_name)

        if CURRENT_COMPUTED is not None:
            if isinstance(value, MutableSequence):
                # Pass None for mutable sequences to prevent memory leaks and
                # ensure in-place mutations bypass the `old != new` check.
                CURRENT_COMPUTED._record_access(instance, self.public_name, None)
            else:
                # there is a computed dependent on this Observable, so let's add
                # this Observable as a parent
                CURRENT_COMPUTED._record_access(instance, self.public_name, value)

            # fixme, this can be done more cleanly
            #  problem here is that we cannot use self (i.e., the observable), we need to add the instance as well
            PROCESSING_SIGNALS.add(_hashable_signal(instance, self.public_name))

        return value

    def __set_name__(self, owner: HasEmitters, name: str):  # noqa: D105
        self.public_name = name
        self.private_name = f"_{name}"

    def __set__(self, instance: HasEmitters, value):  # noqa: D105
        # Nobody listening: skip fetching the old value and building a Message.
        if not instance._has_subscribers(self.public_name, ObservableSignals.CHANGED):
            return
        change_signal = self.signal_types(
            "changed"
        )  # look up "changed" in the descriptor's enum

        # only an on-change signal here; subclasses specify more
        instance.notify(
            self.public_name,
            change_signal,
            old=value,
            new=getattr(instance, self.private_name, self.fallback_value),
        )

    def __str__(self):  # noqa: D105
        return f"{self.__class__.__name__}: {self.public_name}"


class Observable(BaseObservable):
    """Observable descriptor.

    An observable is an attribute that emits ObservableSignals.CHANGED whenever it is changed to a different value.

    """

    signal_types = ObservableSignals

    def __set__(self, instance: HasEmitters, value):  # noqa D103
        if (
            CURRENT_COMPUTED is not None
            and _hashable_signal(instance, self.public_name) in PROCESSING_SIGNALS
        ):
            raise ValueError(
                f"cyclical dependency detected: Computed({CURRENT_COMPUTED.name}) tries to change "
                f"{instance.__class__.__name__}.{self.public_name} while also being dependent on it"
            )

        send_notify = False
        old_value = None
        if instance._has_subscribers(self.public_name, ObservableSignals.CHANGED):
            old_value = getattr(instance, self.private_name, None)
            if old_value != value:
                send_notify = True
        setattr(instance, self.private_name, value)

        if send_notify:
            instance.notify(
                self.public_name,
                ObservableSignals.CHANGED,
                old=old_value,
                new=value,
            )
            PROCESSING_SIGNALS.clear()  # we have notified our children, so we can clear this out


class ComputedState(ComputedStateBase):
    """Internal class to hold the state of a computed property for a specific instance."""

    __slots__ = ()

    def evaluate(self) -> Any:
        """Recompute the value by calling self.func, tracking dependencies as it runs.

        Any Observable read during the call is recorded as a dependency, and
        subscriptions are updated so this state is marked dirty again when
        one of them changes. On success, value is updated and is_dirty is
        cleared.

        Raises:
            Exception: Any exception raised by self.func propagates
                unchanged. parents is restored to its prior state and
                is_dirty is left set, so the caller may retry later.

        Returns:
            The newly computed value.
        """
        global CURRENT_COMPUTED  # noqa: PLW0603

        old_computed = CURRENT_COMPUTED
        # Save and reset PROCESSING_SIGNALS so that `self.func` reading an Observable
        # derived from this same ComputedState (e.g. a rate function reading the
        # ContinuousState it drives) does not trigger a false cyclical-dependency error.
        old_processing = set(PROCESSING_SIGNALS)
        PROCESSING_SIGNALS.clear()
        CURRENT_COMPUTED = self
        old_parents = self.parents
        self.parents = weakref.WeakKeyDictionary()

        try:
            self.value = self.func(self.owner)
        except Exception:
            self.parents = old_parents
            raise
        finally:
            CURRENT_COMPUTED = old_computed
            PROCESSING_SIGNALS.update(old_processing)

        _resubscribe(self, old_parents)

        self.is_dirty = False
        return self.value


def _create_state(
    owner: HasEmitters, key: str, func: Callable, dependencies: Any
) -> ComputedState:
    """Create the ComputedState of func on owner and store it under key."""
    state = ComputedState(owner, func.__name__, func, dependencies=dependencies)
    setattr(owner, key, state)
    return state


def computed_property(
    func: Callable | None = None,
    *,
    dependencies: Iterable[tuple[str, str | SignalType]] | None = None,
) -> property:
    """Decorator to create a computed property.

    Acts like @property, but automatically tracks dependencies (Observables)
    accessed during the function execution and updates them using a diffing engine.

    Args:
        func: The function to be decorated.
        dependencies: Optional iterable of (observable_name, signal_type) tuples to explicitly track.
    """

    def decorator(computation_func):
        key = f"_computed_{computation_func.__name__}"

        @functools.wraps(computation_func)
        def wrapper(self: HasEmitters):
            if not hasattr(self, key):
                state = _create_state(self, key, computation_func, dependencies)
            else:
                state = getattr(self, key)

            if state.is_dirty:
                # Only recompute when a parent actually changed.
                if _parents_changed(state.parents):
                    state.evaluate()
                state.is_dirty = False
            if CURRENT_COMPUTED is not None:
                CURRENT_COMPUTED._record_access(
                    self, computation_func.__name__, state.value
                )
            return state.value

        return ComputedProperty(wrapper)

    # Called with arguments (@computed_property(dependencies=...)) or without.
    return decorator if func is None else decorator(func)
