"""Objects that emit signals: the HasEmitters mixin and the emit decorator.

HasEmitters discovers the observables defined on a class and sends their signals
to weakly referenced subscribers. Registering subscribers is inherited from
SubscriptionMixin. The emit decorator turns a method into a signal source.
"""

from __future__ import annotations

import functools
import weakref
from collections import defaultdict
from collections.abc import Callable, Generator
from typing import Any, ClassVar, Literal

from modelly.time.signals.computed import ComputedProperty
from modelly.time.signals.subscriptions import SubscriptionMixin
from modelly.time.signals.util import Message, SignalType


class HasEmitters(SubscriptionMixin):
    """HasEmitters class.

    Attributes:
        subscribers: mapping of observables/emitters and signal type to subscribers
        observables: mapping of observables/emitters to their available signal types

    HasEmitters automatically discovers the observables/emitters defined on the class.

    """

    # a list of weakrefs: a WeakSet mishandles bound methods, and a list is faster
    subscribers: dict[
        tuple[str, SignalType], list[weakref.ref]
    ]  # (observable_name, signal_type) -> list of weakref subscribers
    observables: dict[str, type[SignalType] | frozenset[SignalType]]

    _class_subscribers: ClassVar[dict[tuple[str, SignalType], list[weakref.ref]]] = (
        defaultdict(list)
    )

    # False once anything may listen; never reset (a stale False is only slower).
    _quiet: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs):
        """Initialize a HasEmitters subclass."""
        super().__init_subclass__(**kwargs)
        cls.observables = dict(descriptor_generator(cls))
        cls._class_subscribers = defaultdict(list)

    def __init__(self, *args, **kwargs) -> None:
        """Initialize a HasEmitters."""
        super().__init__(*args, **kwargs)
        self.subscribers = defaultdict(list)
        self._batch_context = None
        self._suppress = False

    def _has_subscribers(self, name: str, signal_type: str | SignalType) -> bool:
        """Check if there are any subscribers for a given observable and signal type."""
        # Fast path: the overwhelming majority of models never subscribe to
        # anything, so skip the tuple allocation and dict lookups entirely.
        if not self.subscribers and not self._class_subscribers:
            return False
        key = (name, signal_type)
        return bool(self.subscribers.get(key)) or bool(self._class_subscribers.get(key))

    def notify(
        self,
        observable: str,
        signal_type: str | SignalType,
        **kwargs,
    ):
        """Emit a signal.

        Inside a batch the signal is captured by the batch. Otherwise it is only
        built and sent when the observable has live subscribers, and sending it
        prunes subscribers that are no longer alive.

        Args:
            observable: the public name of the observable emitting the signal
            signal_type: the type of signal to emit
            kwargs: additional keyword arguments to include in the signal

        """
        if self._suppress:
            return

        if self._batch_context is not None:
            signal = Message(
                name=observable,
                owner=self,
                signal_type=signal_type,
                additional_kwargs=kwargs,
            )
            self._batch_context.capture(signal)
            return

        if not self._has_subscribers(observable, signal_type):
            return

        signal = Message(
            name=observable,
            owner=self,
            signal_type=signal_type,
            additional_kwargs=kwargs,
        )

        self._modelly_notify(signal)

    def _modelly_notify(self, signal: Message):
        """Send out the signal.

        Args:
        signal: the signal

        Notes:
        signal must contain name and type attributes because this is how observers are stored.

        """
        # we put this into a helper method, so we can emit signals with other fields
        # than the default ones in notify.
        observable = signal.name
        signal_type = signal.signal_type
        key = (observable, signal_type)

        for subs_dict in (self.subscribers, self._class_subscribers):
            observers = subs_dict.get(key, [])
            if not observers:
                continue

            active_observers = []
            for observer in observers:
                if active_observer := observer():
                    active_observer(signal)
                    active_observers.append(observer)

            if active_observers:
                subs_dict[key] = active_observers
            else:
                del subs_dict[key]

    def batch(self):
        """Return a context manager that batches signals.

        Signals emitted during the batch are buffered and aggregated on exit.
        Nested batches merge into the outer batch; only the outermost dispatches.

        Note:
            Computed properties may return stale cached values during the batch.
            They will be updated when aggregated signals are dispatched on exit.

        """
        from modelly.time.signals.batching import _BatchContext  # noqa: PLC0415

        return _BatchContext(self)

    def suppress(self):
        """Return a context manager that suppresses all signals.

        No signals are emitted, buffered, or dispatched during suppression.

        Note:
            Computed properties may become permanently stale because their
            triggering signals are dropped entirely.

        """
        from modelly.time.signals.batching import _SuppressContext  # noqa: PLC0415

        return _SuppressContext(self)

    def peek(self, name: str, default: Any = None) -> Any:
        """Retrieve an attribute without registering it in the dependency graph."""
        # The tracking state lives in core, which imports this module.
        import modelly.time.signals.core as core  # noqa: PLC0415

        prev = core.CURRENT_COMPUTED
        core.CURRENT_COMPUTED = None

        try:
            return getattr(self, name, default)
        finally:
            core.CURRENT_COMPUTED = prev


def descriptor_generator(
    cls,
) -> Generator[tuple[str, type[SignalType] | frozenset[SignalType]]]:
    """Yield the name and signal_types for each Observable defined on cls.

    This handles both legacy BaseObservable descriptors and new @computed_properties.
    """
    # core defines BaseObservable and imports this module.
    from modelly.time.signals.core import BaseObservable  # noqa: PLC0415

    emitters = defaultdict(set)
    for base in cls.__mro__:
        base_dict = vars(base)

        for name, entry in base_dict.items():
            if isinstance(entry, ComputedProperty):
                yield name, entry.signal_types
            elif isinstance(entry, BaseObservable):
                yield entry.public_name, entry.signal_types
            elif hasattr(entry, "_modelly_signal_emitter"):
                observable_name, signal = entry._modelly_signal_emitter
                emitters[observable_name].add(signal)

    for name, signals in emitters.items():
        yield name, frozenset(signals)


def emit(observable_name, signal_to_emit, when: Literal["before", "after"] = "after"):
    """Decorator to emit a signal before or after the call to method (HasEmitters only).

    Args:
        observable_name: the name of the observable that emits the signal
        signal_to_emit: the signal to emit
        when: whether to emit the signal before or after the function call.
    """
    before = when == "before"

    def inner(method):
        """Wrap func; the listener check is inlined since it runs on every agent birth and death."""
        if before:
            wrapper = _emit_before(method, observable_name, signal_to_emit)
        else:
            wrapper = _emit_after(method, observable_name, signal_to_emit)
        wrapper._modelly_signal_emitter = observable_name, signal_to_emit
        return wrapper

    return inner


def _emit_before(method: Callable, observable_name, signal_to_emit) -> Callable:
    """Wrap method so the signal is emitted before the call."""
    key = (observable_name, signal_to_emit)

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if (
            self._suppress
            or self._batch_context is not None
            or self.subscribers.get(key)
            or self._class_subscribers.get(key)
        ):
            self.notify(observable_name, signal_to_emit, args=args, **kwargs)
        return method(self, *args, **kwargs)

    return wrapper


def _emit_after(method: Callable, observable_name, signal_to_emit) -> Callable:
    """Wrap method so the signal is emitted after the call."""
    key = (observable_name, signal_to_emit)

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        ret = method(self, *args, **kwargs)
        if (
            self._suppress
            or self._batch_context is not None
            or self.subscribers.get(key)
            or self._class_subscribers.get(key)
        ):
            self.notify(observable_name, signal_to_emit, args=args, **kwargs)
        return ret

    return wrapper
