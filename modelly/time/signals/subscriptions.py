"""Subscribing to and unsubscribing from the observables of a HasEmitters.

SubscriptionMixin holds the registration side of HasEmitters: validating names
and signal types, and adding or removing weakly referenced handlers at instance
or class level. Emitting signals lives on HasEmitters itself.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from modelly.time.signals.util import ALL, SignalType, create_weakref

ObservableName = str | type(ALL) | Iterable[str]
SignalSpec = str | SignalType | type(ALL) | Iterable[str | SignalType]


class SubscriptionMixin:
    """Observer registration for HasEmitters (instance and class level)."""

    def observe(
        self,
        observable_name: ObservableName,
        signal_type: SignalSpec,
        handler: Callable,
    ):
        """Subscribe to the Observable <name> for signal_type.

        Args:
            observable_name: name of the Observable to subscribe to
            signal_type: the type of signal on the Observable to subscribe to
            handler: the handler to call

        Raises:
            ValueError: if the Observable <name> is not registered or if the Observable
            does not emit the given signal_type

        """
        self._register_observer(self.subscribers, observable_name, signal_type, handler)
        self._quiet = False

    @classmethod
    def _unregister_observer(
        cls,
        subs_dict: dict,
        observable_name: ObservableName,
        signal_type: SignalSpec,
        handler: Callable,
    ):
        """Shared logic to validate and unregister an observer from a dictionary."""
        names = cls._process_name(observable_name)
        target_signals = cls._process_signal_type(signal_type)

        for name in names:
            current_signals = (
                target_signals if target_signals is not None else cls.observables[name]
            )

            for st in current_signals:
                key = (name, st)
                if key in subs_dict:
                    remaining = []
                    for ref in subs_dict[key]:
                        if subscriber := ref():  # noqa: SIM102
                            if subscriber != handler:
                                remaining.append(ref)

                    if remaining:
                        subs_dict[key] = remaining
                    else:
                        del subs_dict[key]

    def unobserve(
        self,
        observable_name: ObservableName,
        signal_type: SignalSpec,
        handler: Callable,
    ):
        """Unsubscribe to the Observable <name> for signal_type.

        Args:
            observable_name: name of the Observable to unsubscribe from
            signal_type: the type of signal on the Observable to unsubscribe to
            handler: the handler that is unsubscribing

        """
        self._unregister_observer(
            self.subscribers, observable_name, signal_type, handler
        )

    @classmethod
    def unobserve_class(
        cls,
        observable_name: ObservableName,
        signal_type: SignalSpec,
        handler: Callable,
    ):
        """Unsubscribe at the class level to the Observable <name> for signal_type.

        Args:
            observable_name: name of the Observable to unsubscribe from
            signal_type: the type of signal on the Observable to unsubscribe to
            handler: the handler that is unsubscribing
        """
        cls._unregister_observer(
            cls._class_subscribers, observable_name, signal_type, handler
        )

    @classmethod
    def _clear_all_subscriptions(cls, subs_dict: dict, name: ObservableName):
        """Shared logic to clear all subscriptions for an observable."""
        if name is ALL:
            subs_dict.clear()
        elif isinstance(name, str):
            keys_to_remove = [k for k in subs_dict if k[0] == name]
            for k in keys_to_remove:
                del subs_dict[k]
        else:
            for n in name:
                keys_to_remove = [k for k in subs_dict if k[0] == n]
                for k in keys_to_remove:
                    del subs_dict[k]

    def clear_all_subscriptions(self, name: ObservableName):
        """Clears all instance-level subscriptions for the observable <name>.

        if name is ALL, all subscriptions are removed

        Args:
            name: name of the Observable to unsubscribe for all signal types

        """
        self._clear_all_subscriptions(self.subscribers, name)

    @classmethod
    def clear_all_class_subscriptions(cls, name: ObservableName):
        """Clears all class-level subscriptions for the observable <name>.

        if name is ALL, all subscriptions are removed

        Args:
            name: name of the Observable to unsubscribe for all signal types
        """
        cls._clear_all_subscriptions(cls._class_subscribers, name)

    @classmethod
    def _process_name(cls, name: ObservableName) -> Iterable[str]:
        """Convert name to an iterable of observable names."""
        if name is ALL:
            return cls.observables.keys()
        elif isinstance(name, str):
            return [name]
        else:
            return name

    @classmethod
    def _process_signal_type(
        cls, signal_type: SignalSpec
    ) -> Iterable[SignalType] | None:
        """Convert signal_type to an iterable of signal types."""
        if signal_type is ALL:
            return None  # None is used to indicate all signal types
        if isinstance(signal_type, (str, SignalType)):
            return [signal_type]
        else:
            return signal_type

    @classmethod
    def observe_class(
        cls,
        observable_name: ObservableName,
        signal_type: SignalSpec,
        handler: Callable,
    ):
        """Subscribe at the class level to the Observable <name> for signal_type.

        All instances of this class will trigger the handler when they emit this signal.
        Handlers are stored as weak references to prevent memory leaks during experiments.

        Args:
            observable_name: name of the Observable to subscribe to
            signal_type: the type of signal on the Observable to subscribe to
            handler: the handler to call
        """
        cls._register_observer(
            cls._class_subscribers, observable_name, signal_type, handler
        )
        cls._quiet = False

    @classmethod
    def _register_observer(
        cls,
        subs_dict: dict,
        observable_name: ObservableName,
        signal_type: SignalSpec,
        handler: Callable,
    ):
        """Shared logic to validate and register an observer to a dictionary."""
        names = cls._process_name(observable_name)
        target_signals = cls._process_signal_type(signal_type)

        for name in names:
            if name not in cls.observables:
                raise ValueError(
                    f"you are trying to subscribe to {name}, but this Observable is not known"
                )

            current_signals = (
                target_signals if target_signals is not None else cls.observables[name]
            )

            for st in current_signals:
                if st not in cls.observables[name]:
                    raise ValueError(f"Signal {st} not supported by {name}")

            ref = create_weakref(handler)
            for st in current_signals:
                subs_dict[(name, st)].append(ref)
