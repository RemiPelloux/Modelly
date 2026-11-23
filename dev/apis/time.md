# Time

`modelly.time` holds the event list, events and event generators, the scheduling methods of the model, and signals (observables that notify subscribers when they change).

Module

Contents

modelly.time.events

Event, EventList, EventGenerator, Schedule, Priority

modelly.time.schedule

HasSchedule: step, run_for, run_until, schedule_event, schedule_recurring on the model

modelly.time.signals

Observable, HasEmitters, computed_property, ObservableList, the signal types

## Events

Single simulation events and their priorities.

- Priority: An enumeration defining event priority levels (HIGH, DEFAULT, LOW)
- Event: A class representing individual events with timing and execution details

Events hold a weak reference to their callable, so canceled or orphaned events do not keep agents alive.

#### `class Priority(*values)`

Enumeration of priority levels.

#### `class Event(time: int | float, function: Callable[[...], None], priority: Priority = Priority.DEFAULT, function_args: list[Any] | None = None, function_kwargs: dict[str, Any] | None = None)`

A simulation event.

The callable is wrapped using weakref, so there is no need to explicitly cancel event if e.g., an agent is removed from the simulation.

**Variables:**

- **time** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – The simulation time of the event
- **fn** (*Callable*) – The function to execute for this event
- **priority** ([*Priority*](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.events.event.Priority)) – The priority of the event
- **unique_id** ([*int*](https://docs.python.org/3/builtins/functions.html#int))
- **list****[****Any****]** (*function_args*) – Argument for the function
- **Any****]** (*function_kwargs dict**[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*,*) – Keyword arguments for the function

Notes

Simulation events use a weak reference to the callable. If the callback no longer exists at execution time (e.g., because an agent has been removed), execution will fail silently. Lambda callbacks are rejected at Event creation.

Initialize a simulation event.

**Parameters:**

- **time** – the instant of time of the simulation event
- **function** – the callable to invoke
- **priority** – the priority of the event
- **function_args** – arguments for callable
- **function_kwargs** – keyword arguments for the callable

#### `execute() → None`

Execute this event.

#### `cancel() → None`

Cancel this event.

The event list: a heap-based priority queue of simulation events.

Events are kept in chronological order, respecting priorities. Cancellation is lazy, so the heap invariant is never broken, and the heap compacts itself once canceled events dominate it. The heap itself is `modelly._native.events.EventHeap`: compiled when available, with an identical pure-Python twin.

#### `class EventList`

An event list.

This is a heap queue sorted list of events. Events are always removed from the left, so a binary heap is a performant and appropriate data structure. Events are sorted based on their time stamp, their priority, and their unique_id as a tie-breaker, guaranteeing a complete ordering.

Canceling an event leaves it on the heap so the heap invariant is not broken. Models that repeatedly cancel and reschedule an event would therefore grow the heap without bound, so the list counts the canceled events it holds and rebuilds itself once they dominate. That count also makes len() an O(1) operation.

**Variables:**

**COMPACTION_RATIO** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – Fraction of canceled events above which the heap is rebuilt, which also bounds the peak heap at L / (1 - COMPACTION_RATIO)

Notes

An event belongs to one event list at a time. Adding the same event to a second list hands ownership over, and the first list’s count goes stale. An event’s time and priority must not change while it is on a list.

Initialize an event list.

#### `add_event(event: Event)`

Add the event to the event list.

**Parameters:**

**event** ([*Event*](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.events.event.Event)) – The event to be added

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If the event has already been canceled. Cancellation is terminal, so such an event could never execute.

#### `peek_ahead(n: int = 1) → list[Event]`

Look at the first n non-canceled event in the event list.

**Parameters:**

**n** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – The number of events to look ahead

**Returns:**

list[Event]

**Raises:**

[**IndexError**](https://docs.python.org/3/builtins/exceptions.html#IndexError) – If the eventlist is empty

Notes

this method can return a list shorted then n if the number of non-canceled events on the event list is less than n.

#### `pop_event() → Event`

Pop the first element from the event list.

#### `compact() → None`

Remove all canceled events from the heap and rebuild it.

If there are many canceled events, compaction can speed up performance substantially.

#### `is_empty() → bool`

Return whether the event list is empty.

#### `remove(event: Event) → None`

Remove an event from the event list.

**Parameters:**

**event** ([*Event*](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.events.event.Event)) – The event to be removed

#### `clear() → None`

Clear the event list, detaching the events so a later cancel() is not counted.

Recurring events: a Schedule describes when, an EventGenerator makes it happen.

#### `class Schedule(interval: float | int | Callable[[Model], float | int] = 1.0, start: float | None = None, end: float | None = None, count: int | None = None)`

Defines when something should happen repeatedly.

**Variables:**

- **interval** ([*float*](https://docs.python.org/3/builtins/functions.html#float)* | *[*int*](https://docs.python.org/3/builtins/functions.html#int)* | **Callable**[**[*[*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)*]**, *[*float*](https://docs.python.org/3/builtins/functions.html#float)* | *[*int*](https://docs.python.org/3/builtins/functions.html#int)*]*) – Time between executions (fixed value or callable returning value)
- **start** ([*float*](https://docs.python.org/3/builtins/functions.html#float)* | **None*) – Absolute time to begin (None = use current model time + interval)
- **end** ([*float*](https://docs.python.org/3/builtins/functions.html#float)* | **None*) – Absolute time to stop (None = no end)
- **count** ([*int*](https://docs.python.org/3/builtins/functions.html#int)* | **None*) – Maximum executions (None = unlimited)

#### `class EventGenerator(model: Model, function: Callable[..., None], schedule: Schedule, priority: Priority = Priority.DEFAULT)`

A generator that creates recurring events based on a Schedule.

Unlike a single Event, an EventGenerator is persistent and can be stopped or configured with stop conditions.

**Variables:**

- **model** – The model this generator belongs to
- **function** – The callable to execute for each generated event
- **schedule** – The Schedule defining when events occur
- **priority** – Priority level for generated events

Notes

Event generators use a weak reference to the callable. Therefore, you cannot pass a lambda function in fn. A simulation event where the callable no longer exists (e.g., because the agent has been removed from the model) will fail silently. If you want to use functools.partial, please assign the partial function to a variable prior to creating the generator.

Initialize an EventGenerator.

**Parameters:**

- **model** – The model this generator belongs to
- **function** – The callable to execute for each generated event. Use functools.partial to bind arguments.
- **schedule** – The Schedule defining timing
- **priority** – Priority level for generated events

#### `property is_active: bool`

Return whether the generator is currently active.

#### `property execution_count: int`

Return the number of times this generator has executed.

#### `property next_scheduled_time: float | None`

Return the time of the next scheduled execution, or None if not scheduled.

#### `start() → EventGenerator`

Start the event generator.

**Returns:**

Self for method chaining

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If schedule.start is in the past, e.g. when restarting a stopped generator after its start time has passed.

#### `stop() → None`

Stop the event generator immediately.

#### `pause() → None`

Pause the event generator temporarily.

This cancels the currently scheduled event but keeps the generator active in the model. Execution can be resumed later using resume().

#### `resume() → None`

Resume a paused event generator.

## Scheduling on the model

`Model` inherits these methods; they are also listed on the [Core](https://remipelloux.github.io/Modelly/dev/apis/core.html) page.

Event scheduling and time advance for [`modelly.core.model.Model`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model).

A mixin so the model file stays readable; every method here needs the model’s `_event_list`, `_event_generators`, `time` and signals.

#### `class HasSchedule`

Scheduling, running and time advance, mixed into `Model`.

#### `schedule_event(function: Callable, *, at: float | None = None, after: float | None = None, priority: Priority = Priority.DEFAULT) → Event`

Schedule a one-off event.

**Parameters:**

- **function** – The callable to execute
- **at** – Absolute time to execute (mutually exclusive with after)
- **after** – Relative time from now to execute (mutually exclusive with at)
- **priority** – Priority level for the event

**Returns:**

The scheduled Event (can be used to cancel)

**Raises:**

- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If both or neither of at/after are specified
- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If both or neither of at/after are specified, or if the scheduled time is in the past.

#### `schedule_recurring(function: Callable, schedule: Schedule, priority: Priority = Priority.DEFAULT) → EventGenerator`

Schedule a recurring event based on a Schedule.

**Parameters:**

- **function** – The callable to execute repeatedly
- **schedule** – The Schedule defining when events occur
- **priority** – Priority level for generated events

**Returns:**

The EventGenerator (can be used to stop)

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If the schedule start time is in the past.

#### `run_for(duration: float | int) → None`

Run the model for the specified duration.

**Parameters:**

**duration** – Time units to advance

#### `run_until(end_time: float | int) → None`

Run the model until the specified time.

**Parameters:**

**end_time** – Absolute time to run until

If model.time is larger than end_time, the method returns directly.

## Signals

`HasEmitters` takes its subscription methods (`observe`, `unobserve`, `observe_class`, …) from `modelly.time.signals.subscriptions`; they are listed under `HasEmitters`.

Core implementation of Modelly’s reactive programming system.

This module provides the foundational classes for Modelly’s observable/reactive programming functionality:

- BaseObservable: Abstract base class defining the interface for all observables
- Observable: Main class for creating observable properties that emit change signals
- computed_property: Decorator for creating properties that automatically update based on dependencies
- HasEmitters: Mixin class that enables an object to contain and manage observables
- emit: Decorator for methods that emit signals

The module implements a robust reactive system where changes to observable properties automatically trigger updates to dependent computed values and notify subscribed observers. This enables building models with complex interdependencies while maintaining clean separation of concerns.

It also owns the dependency-tracking state (CURRENT_COMPUTED, PROCESSING_SIGNALS), so everything that reads or rebinds that state is defined here.

#### `class BaseObservable(fallback_value=None)`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Base class for all Observables.

Initialize a BaseObservable.

#### `signal_types`

alias of [`SignalType`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.util.SignalType)

#### `class Observable(fallback_value=None)`

Bases: [`BaseObservable`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.core.BaseObservable)

Observable descriptor.

An observable is an attribute that emits ObservableSignals.CHANGED whenever it is changed to a different value.

Initialize a BaseObservable.

#### `signal_types`

alias of [`ObservableSignals`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.types.ObservableSignals)

#### `computed_property(func: Callable | None = None, *, dependencies: Iterable[tuple[str, str | SignalType]] | None = None) → property`

Decorator to create a computed property.

Acts like @property, but automatically tracks dependencies (Observables) accessed during the function execution and updates them using a diffing engine.

**Parameters:**

- **func** – The function to be decorated.
- **dependencies** – Optional iterable of (observable_name, signal_type) tuples to explicitly track.

#### `class ComputedState(owner: HasEmitters, name: str, func: Callable, dependencies: Iterable[tuple[str, str | SignalType]] | None = None)`

Bases: [`ComputedStateBase`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.computed.ComputedStateBase)

Internal class to hold the state of a computed property for a specific instance.

Initialize a ComputedState.

**Parameters:**

- **owner** – the HasEmitters instance on which this state is defined
- **name** – the name of the computed property
- **func** – the computation function
- **dependencies** – optional iterable of explicit dependencies to track

#### `evaluate() → Any`

Recompute the value by calling self.func, tracking dependencies as it runs.

Any Observable read during the call is recorded as a dependency, and subscriptions are updated so this state is marked dirty again when one of them changes. On success, value is updated and is_dirty is cleared.

**Raises:**

[**Exception**](https://docs.python.org/3/builtins/exceptions.html#Exception) – Any exception raised by self.func propagates unchanged. parents is restored to its prior state and is_dirty is left set, so the caller may retry later.

**Returns:**

The newly computed value.

Objects that emit signals: the HasEmitters mixin and the emit decorator.

HasEmitters discovers the observables defined on a class and sends their signals to weakly referenced subscribers. Registering subscribers is inherited from SubscriptionMixin. The emit decorator turns a method into a signal source.

#### `class HasEmitters(*args, **kwargs)`

HasEmitters class.

**Variables:**

- **subscribers** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*modelly.time.signals.util.SignalType*](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.util.SignalType)*]**, *[*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*weakref.ReferenceType*](https://docs.python.org/3/library/weakref.html#weakref.ReferenceType)*]**]*) – mapping of observables/emitters and signal type to subscribers
- **observables** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*type*](https://docs.python.org/3/builtins/functions.html#type)*[*[*modelly.time.signals.util.SignalType*](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.util.SignalType)*] **| *[*frozenset*](https://docs.python.org/3/builtins/stdtypes.html#frozenset)*[*[*modelly.time.signals.util.SignalType*](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.util.SignalType)*]**]*) – mapping of observables/emitters to their available signal types

HasEmitters automatically discovers the observables/emitters defined on the class.

Initialize a HasEmitters.

#### `notify(observable: str, signal_type: str | SignalType, **kwargs)`

Emit a signal.

Inside a batch the signal is captured by the batch. Otherwise it is only built and sent when the observable has live subscribers, and sending it prunes subscribers that are no longer alive.

**Parameters:**

- **observable** – the public name of the observable emitting the signal
- **signal_type** – the type of signal to emit
- **kwargs** – additional keyword arguments to include in the signal

#### `batch()`

Return a context manager that batches signals.

Signals emitted during the batch are buffered and aggregated on exit. Nested batches merge into the outer batch; only the outermost dispatches.

Note

Computed properties may return stale cached values during the batch. They will be updated when aggregated signals are dispatched on exit.

#### `suppress()`

Return a context manager that suppresses all signals.

No signals are emitted, buffered, or dispatched during suppression.

Note

Computed properties may become permanently stale because their triggering signals are dropped entirely.

#### `peek(name: str, default: Any = None) → Any`

Retrieve an attribute without registering it in the dependency graph.

#### `classmethod clear_all_class_subscriptions(name: str | _AllSentinel | Iterable[str])`

Clears all class-level subscriptions for the observable <name>.

if name is ALL, all subscriptions are removed

**Parameters:**

**name** – name of the Observable to unsubscribe for all signal types

#### `clear_all_subscriptions(name: str | _AllSentinel | Iterable[str])`

Clears all instance-level subscriptions for the observable <name>.

if name is ALL, all subscriptions are removed

**Parameters:**

**name** – name of the Observable to unsubscribe for all signal types

#### `observe(observable_name: str | _AllSentinel | Iterable[str], signal_type: str | SignalType | _AllSentinel | Iterable[str | SignalType], handler: Callable)`

Subscribe to the Observable <name> for signal_type.

**Parameters:**

- **observable_name** – name of the Observable to subscribe to
- **signal_type** – the type of signal on the Observable to subscribe to
- **handler** – the handler to call

**Raises:**

- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – if the Observable <name> is not registered or if the Observable
- **does not emit the given signal_type** –

#### `classmethod observe_class(observable_name: str | _AllSentinel | Iterable[str], signal_type: str | SignalType | _AllSentinel | Iterable[str | SignalType], handler: Callable)`

Subscribe at the class level to the Observable <name> for signal_type.

All instances of this class will trigger the handler when they emit this signal. Handlers are stored as weak references to prevent memory leaks during experiments.

**Parameters:**

- **observable_name** – name of the Observable to subscribe to
- **signal_type** – the type of signal on the Observable to subscribe to
- **handler** – the handler to call

#### `unobserve(observable_name: str | _AllSentinel | Iterable[str], signal_type: str | SignalType | _AllSentinel | Iterable[str | SignalType], handler: Callable)`

Unsubscribe to the Observable <name> for signal_type.

**Parameters:**

- **observable_name** – name of the Observable to unsubscribe from
- **signal_type** – the type of signal on the Observable to unsubscribe to
- **handler** – the handler that is unsubscribing

#### `classmethod unobserve_class(observable_name: str | _AllSentinel | Iterable[str], signal_type: str | SignalType | _AllSentinel | Iterable[str | SignalType], handler: Callable)`

Unsubscribe at the class level to the Observable <name> for signal_type.

**Parameters:**

- **observable_name** – name of the Observable to unsubscribe from
- **signal_type** – the type of signal on the Observable to unsubscribe to
- **handler** – the handler that is unsubscribing

#### `descriptor_generator(cls) → Generator[tuple[str, type[SignalType] | frozenset[SignalType]]]`

Yield the name and signal_types for each Observable defined on cls.

This handles both legacy BaseObservable descriptors and new @computed_properties.

#### `emit(observable_name, signal_to_emit, when: Literal['before', 'after'] = 'after')`

Decorator to emit a signal before or after the call to method (HasEmitters only).

**Parameters:**

- **observable_name** – the name of the observable that emits the signal
- **signal_to_emit** – the signal to emit
- **when** – whether to emit the signal before or after the function call.

Dependency bookkeeping for computed properties.

These helpers keep a ComputedState’s subscriptions in step with the observables it reads. They hold no tracking state themselves: the currently evaluating computed lives in `modelly.time.signals.core`.

#### `class ComputedProperty(fget=None, fset=None, fdel=None, doc=None)`

A custom property class to identify computed properties.

#### `signal_types`

alias of [`ObservableSignals`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.types.ObservableSignals)

#### `class ComputedStateBase(owner: HasEmitters, name: str, func: Callable, dependencies: Iterable[tuple[str, str | SignalType]] | None = None)`

The per-instance data of a computed property; core.ComputedState adds evaluation.

Initialize a ComputedState.

**Parameters:**

- **owner** – the HasEmitters instance on which this state is defined
- **name** – the name of the computed property
- **func** – the computation function
- **dependencies** – optional iterable of explicit dependencies to track

Observable collection types that emit signals when modified.

This module extends Modelly’s reactive programming capabilities to collection types like lists. Observable collections emit signals when items are added, removed, or modified, allowing other components to react to changes in the collection’s contents.

The module provides: - ListSignals: Enum defining signal types for list collections - ObservableList: A list descriptor that emits signals on modifications - SignalingList: The underlying list implementation that manages signal emission

These classes enable building models where components need to track and react to changes in collections of agents, resources, or other model elements.

#### `class ObservableList`

Bases: [`BaseObservable`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.core.BaseObservable)

An ObservableList that emits signals on changes to the underlying list.

Initialize the ObservableList.

#### `signal_types`

alias of [`ListSignals`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.types.ListSignals)

Batching and suppression of signals for modelly signals.

This module provides context managers for controlling signal dispatch:

- batch(): Buffers signals and dispatches aggregated results on exit
- suppress(): Silently drops all signals during the context

Both batch() and suppress() are used as context managers within HasEmitters. They only batch or suppress signals emitted by the instance within which they are invoked.

It also provides a functools.singledispatch aggregation system for different signal types, making it easy for users to add aggregations for their own custom signal types:

```default
@aggregate.register(MySignalType)
def _my_aggregate(signal_type, signals, value=None):
    ...
```

Notes

During a batch, computed properties may return stale cached values because their triggering signals are deferred. At flush, aggregated signals dispatch normally and mark computed properties dirty.

During suppress, computed properties may become permanently stale because their triggering signals are dropped entirely.]]

@aggregate.register is global to the python process, and it’s non-trivial to remove it, although you can overwrite it. See also functools.singledispatch for more details.

#### `aggregate(signal_type: SignalType, signals: list[Message], value: Any = None) → list[Message]`

#### `aggregate(signal_type: ObservableSignals, signals: list[Message], value: Any = None) → list[Message]`

#### `aggregate(signal_type: ListSignals, signals: list[Message], value: Any = None) → list[Message]`

Default aggregation: keep all signals as-is.

Users can register custom aggregators for their own signal types:

```default
@aggregate.register(MySignalType)
def _my_aggregate(signal_type, signals, value=None):
    ...
```

Notes

we need signal_type as the first argument because that is how singledispatch can determine which handler to call.

**Parameters:**

- **signal_type** – the type of signal (used for dispatch)
- **signals** – list of buffered Message objects
- **value** – the attribute value captured at the time of the first signal, or None if not captured

**Returns:**

list of Message objects to dispatch

Signal types.

#### `class ObservableSignals(*values)`

Bases: [`SignalType`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.util.SignalType)

Enumeration of signal types that observables can emit.

This enum provides type-safe signal type definitions with IDE autocomplete support. Inherits from str for backward compatibility with existing string-based code.

**Variables:**

**CHANGED** – Emitted when an observable’s value changes.

Examples

```default
>>> from modelly.time.signals import Observable, HasEmitters, ObservableSignals
>>> class MyModel(HasEmitters):
...     value = Observable()
...     def __init__(self):
...         super().__init__()
...         self._value = 0
>>> model = MyModel()
>>> def handler(signal):
...     print(signal.additional_kwargs["new"])
>>> model.observe("value", ObservableSignals.CHANGED, handler)
>>> model.value = 10
10
```

Note

String-based signal types are still supported for backward compatibility: >>> model.observe(“value”, “changed”, handler) # Still works

#### `class ListSignals(*values)`

Bases: [`SignalType`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.util.SignalType)

Enumeration of signal types that observable lists can emit.

Provides list-specific signal types with IDE autocomplete and type safety. Inherits from str for backward compatibility with existing string-based code. Includes all list-specific signals (INSERTED, APPENDED, REMOVED, REPLACED) plus a SET signal for when the entire list is modified.

**Variables:**

- **SET** – Emitted when the list itself is replaced/assigned.
- **INSERTED** – Emitted when an item is inserted into the list.
- **APPENDED** – Emitted when an item is appended to the list.
- **REMOVED** – Emitted when an item is removed from the list.
- **REPLACED** – Emitted when an item is replaced/modified in the list.

Examples

```default
>>> from modelly.time.signals import ObservableList, HasEmitters, ListSignals
>>> class MyModel(HasEmitters):
...     items = ObservableList()
...     def __init__(self):
...         super().__init__()
...         self.items = []
>>> model = MyModel()
>>> def handler(message):
...     print(f"Inserted {message.additional_kwargs['new']}")
>>> model.observe("items", ListSignals.INSERTED, handler)
>>> model.items.insert(0, "first")
Inserted first
```

Note

String-based signal types are still supported for backward compatibility: >>> model.observe(“items”, “inserted”, handler) # Still works

#### `class ModelSignals(*values)`

Bases: [`SignalType`](https://remipelloux.github.io/Modelly/dev/apis/time.html#modelly.time.signals.util.SignalType)

Signal types for model-level events.

Utility functions and classes for Modelly’s signals implementation.

This module provides helper functionality used by Modelly’s reactive programming system:

- Message: a dataclass containing information about a signal change
- SignalType: root enum defining the types of signals that can be emitted
- create_weakref: Helper function to properly create weak references to different types
- _AllSentinel class for subscribing to all signals or all observables

These utilities support the core signals implementation by providing reference management and convenient data structures used throughout the reactive system.

#### `class Message(name: str, owner: Any, signal_type: SignalType, additional_kwargs: dict)`

A message class containing information about a signal change.

Set the fields through their slots.

The frozen dataclass’s generated `__init__` sets each field through `object.__setattr__`; writing the slots directly is the same state, about 60 ns cheaper per message (a message is built per dispatched signal).

#### `class SignalType(new_class_name, /, names, *, module=None, qualname=None, type=None, start=1, boundary=None)`

Root class for all signal type enums.

#### `create_weakref(item, callback=None)`

Helper function to create a correct weakref for any item.
