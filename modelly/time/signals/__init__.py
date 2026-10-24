"""Modelly Signals (Observables) package that provides reactive programming capabilities.

This package enables tracking changes to properties and state in Modelly models through a
reactive programming paradigm. It enables building models where components can observe
and react to changes in other components' state.

The package provides the core Observable classes and utilities needed to implement
reactive patterns in agent-based models. This includes capabilities for watching changes
to attributes, computing derived values, and managing collections that emit signals
when modified.
"""

from modelly.time.signals.batching import aggregate
from modelly.time.signals.collections import ObservableList
from modelly.time.signals.core import (
    HasEmitters,
    Observable,
    computed_property,
    emit,
)
from modelly.time.signals.types import ListSignals, ModelSignals, ObservableSignals
from modelly.time.signals.util import ALL, Message, SignalType

__all__ = [
    "ALL",
    "HasEmitters",
    "ListSignals",
    "Message",
    "ModelSignals",
    "Observable",
    "ObservableList",
    "ObservableSignals",
    "SignalType",
    "aggregate",
    "computed_property",
    "emit",
]
