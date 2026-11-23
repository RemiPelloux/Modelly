# Core

`modelly.core` holds the model, agents, agent sets, columns, the random source and the exceptions. `modelly.Model`, `modelly.Agent`, `modelly.Column` and `modelly.FastRandom` are the same objects as `modelly.core.Model`, `modelly.core.Agent` and so on.

Module

Contents

modelly.core.model

Model

modelly.core.registry

the agent registries the model inherits (agents, agents_by_type, agent_types)

modelly.core.agent

Agent

modelly.core.agentset

AgentSet, AbstractAgentSet, GroupBy

modelly.core.columns, modelly.core.column_access

Column and the column tables

modelly.core.rng

FastRandom, PyFastRandom

modelly.core.checkpoint

the checkpoint file format behind Model.save and Model.load

modelly.core.exceptions

the exceptions raised by Modelly

## Model

`Model` takes its agent registries from `modelly.core.registry`, its scheduling methods from `modelly.time.schedule` and its signals from `modelly.time.signals`; all of them are listed below.

The model class for Modelly framework.

Core Objects: Model

#### `class Model(*args: Any, rng: RNGLike | SeedLike | None = None, scenario: S | type[S] = <class 'modelly.scenarios.scenario.Scenario'>, **kwargs: Any)`

Base class for models in the Modelly ABM library.

This class serves as a foundational structure for creating agent-based models. It includes the basic attributes and methods necessary for initializing and running a simulation model.

**Type Parameters:**

A: The agent type used in this model S: The scenario type used in this model

**Variables:**

- **running** – A boolean indicating if the model should continue running.
- **time** – the current simulation time.
- **random** – a seeded python.random number generator.
- **rng** – a seeded numpy.random.Generator
- **scenario** – the scenario instance containing model parameters

Notes

Model.agents returns the AgentSet containing all agents registered with the model. Changing the content of the AgentSet directly can result in strange behavior. If you want change the composition of this AgentSet, ensure you operate on a copy.

Create a new model.

Overload this method with the actual code to initialize the model. Always start with super().__init__() to initialize the model object properly.

**Parameters:**

- **args** – arguments to pass onto super
- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). Ignored if a Scenario instance is passed; used to instantiate the scenario when a Scenario class is passed.
- **scenario** – A Scenario instance or subclass to use for this model. If a class is passed it is instantiated with rng. If an instance is passed, rng must not be set.
- **kwargs** – keyword arguments to pass onto super

Notes

Pass either rng or a Scenario instance, not both. Passing rng alongside a Scenario class is valid — rng is forwarded to the class constructor.

#### `property scenario: S`

Return scenario instance.

#### `run_model() → None`

Run the model until the end condition is reached.

Overload as needed.

#### `step() → None`

A single step. Fill in here.

#### `save(path: str | Path, *, compress: bool = False) → None`

Save the whole model to one checkpoint file.

The file holds the agents, spaces, columns, scheduled events, data collected so far and the exact state of `random` and `rng`, so `Model.load` resumes the run draw for draw.

**Parameters:**

- **path** – The file to write.
- **compress** – Gzip the payload (smaller, slower).

**Raises:**

[**CheckpointError**](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.CheckpointError) – If a callback the model holds, such as an event callback or a reporter, is a lambda or nested function.

#### `classmethod load(path: str | Path) → Self`

Load a model saved with `save`.

Warning

A checkpoint is a pickle: loading one runs code chosen by whoever wrote it. Only load files you created or otherwise trust.

**Parameters:**

**path** – The checkpoint file.

**Returns:**

The saved model, an instance of the class it was saved from.

**Raises:**

[**CheckpointError**](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.CheckpointError) – If the file is not a checkpoint, was written by another Modelly or Python release, or holds no `cls`.

#### `checkpoint_every(interval: float, path_pattern: str, *, compress: bool = False) → CheckpointWriter`

Save a checkpoint every `interval` time units.

**Parameters:**

- **interval** – Time between checkpoints; the first is `interval` from now.
- **path_pattern** – The file name, formatted with `time`, e.g. `"run-{time:04.0f}.ckpt"`.
- **compress** – Gzip each checkpoint.

**Returns:**

The writer; call its `stop()` to end the checkpoints.

#### `property agent_types: list[type]`

Return a list of all unique agent types registered with the model.

#### `property agents: _HardKeyAgentSet[A]`

Provides a _HardKeyAgentSet of all agents in the model, combining agents from all types.

**Returns:**

The agent set containing all agents with strong references.

**Return type:**

_HardKeyAgentSet

Warning

This returns the actual internal _HardKeyAgentSet used by Modelly for agent registration and tracking. It uses strong references to prevent premature garbage collection and reduce performance overhead caused by weak reference management.

**Do not modify this AgentSet directly** (e.g., by adding or removing agents manually). Direct modifications can break the model’s agent tracking system and cause unexpected behavior. Instead:

- Use `Agent()` to create new agents (automatically registers them)
- Use `agent.remove()` to remove agents (automatically deregisters them)
- For read-only operations or transformations, work on a copy: `model.agents.copy()`

Notes

This is Modelly’s core agent registration system. All agents created via `Agent.__init__` are automatically registered here.

#### `property agents_by_type: dict[type[A], _HardKeyAgentSet[A]]`

A dictionary where keys are agent types and values are the corresponding _HardKeyAgentSets.

**Returns:**

Dictionary mapping agent types to their AgentSets.

**Return type:**

[dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[type](https://docs.python.org/3/builtins/functions.html#type)[A], _HardKeyAgentSet[A]]

Warning

Each AgentSet in this dictionary is a _HardKeyAgentSet with strong references, forming part of Modelly’s core agent registration system.

**Do not modify these AgentSets directly**. Direct modifications can break agent tracking and cause unexpected behavior. Instead:

- Use `Agent()` to create new agents (automatically registers them)
- Use `agent.remove()` to remove agents (automatically deregisters them)
- For read-only operations, work on copies: `model.agents_by_type[AgentType].copy()`

Notes

This is part of Modelly’s core agent registration system. All agents are automatically registered in the appropriate type-specific AgentSet when created via `Agent.__init__`.

#### `batch()`

Return a context manager that batches signals.

Signals emitted during the batch are buffered and aggregated on exit. Nested batches merge into the outer batch; only the outermost dispatches.

Note

Computed properties may return stale cached values during the batch. They will be updated when aggregated signals are dispatched on exit.

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

#### `deregister_agent(agent: A)`

Deregister the agent with the model.

**Parameters:**

**agent** – The agent to deregister.

Notes

This method is called automatically by `Agent.remove`

#### `notify(observable: str, signal_type: str | SignalType, **kwargs)`

Emit a signal.

Inside a batch the signal is captured by the batch. Otherwise it is only built and sent when the observable has live subscribers, and sending it prunes subscribers that are no longer alive.

**Parameters:**

- **observable** – the public name of the observable emitting the signal
- **signal_type** – the type of signal to emit
- **kwargs** – additional keyword arguments to include in the signal

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

#### `peek(name: str, default: Any = None) → Any`

Retrieve an attribute without registering it in the dependency graph.

#### `register_agent(agent: A)`

Register the agent with the model.

**Parameters:**

**agent** – The agent to register.

Notes

This method is called automatically by `Agent.__init__`, so there is no need to use this if you are subclassing Agent and calling its super in the `__init__` method.

#### `remove_all_agents()`

Remove all agents from the model.

Notes

This method calls agent.remove for all agents in the model. If you need to remove agents from e.g., a SingleGrid, you can either explicitly implement your own agent.remove method or clean this up near where you are calling this method.

#### `run_for(duration: float | int) → None`

Run the model for the specified duration.

**Parameters:**

**duration** – Time units to advance

#### `run_until(end_time: float | int) → None`

Run the model until the specified time.

**Parameters:**

**end_time** – Absolute time to run until

If model.time is larger than end_time, the method returns directly.

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

#### `suppress()`

Return a context manager that suppresses all signals.

No signals are emitted, buffered, or dispatched during suppression.

Note

Computed properties may become permanently stale because their triggering signals are dropped entirely.

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

## Agent

Agent related classes.

Core Objects: Agent.

#### `class Agent(model: M, *args, **kwargs)`

Base class for a model agent in Modelly.

**Variables:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – A reference to the model instance.
- **unique_id** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – A unique identifier for this agent.

Notes

Agents must be hashable to be used in an AgentSet. In Python 3, defining __eq__ without __hash__ makes an object unhashable, which will break AgentSet usage. unique_id is unique relative to a model instance and starts from 1

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `classmethod column_specs() → dict[str, Column]`

The `Column` declarations of this class (name to column), in table order.

On the class, a column attribute is the fast property that reads the agent’s row; this returns the declarations themselves (dtype, default).

#### `remove() → None`

Remove and delete the agent from the model.

#### `step() → None`

A single step of the agent.

#### `classmethod create_agents(model: Model, n: int, *args, **kwargs) → AgentSet[T]`

Create N agents.

**Parameters:**

- **model** – the model to which the agents belong
- **args** – arguments to pass onto agent instances each arg is either a single object or a sequence of length n
- **n** – the number of agents to create
- **kwargs** – keyword arguments to pass onto agent instances each keyword arg is either a single object or a sequence of length n

**Returns:**

AgentSet containing the agents created.

Warning

A list, tuple, ndarray, or pandas Series argument is treated as one value per agent and must have length n; a length mismatch raises ValueError. This is especially easy to hit with coordinate tuples: create_agents(model, 2, pos=(10, 20)) does NOT give both agents pos=(10, 20); it gives agent 0 pos=10 and agent 1 pos=20, since the tuple’s length (2) matches n (2).

To assign the same sequence value to every agent, broadcast it explicitly as a length-n list of that value, e.g.: create_agents(model, 2, pos=[(10, 20)] * 2)

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If a sequence argument’s length does not match n.

#### `classmethod from_dataframe(model: Model, df: pd.DataFrame, **kwargs) → AgentSet[T]`

Create agents from a pandas DataFrame.

Each row of the DataFrame represents one agent. The DataFrame columns are mapped to the agent’s constructor as keyword arguments. Additional keyword arguments (**kwargs) can be used to set constant attributes for all agents.

**Parameters:**

- **model** – The model instance.
- **df** – The pandas DataFrame. Each row represents an agent.
- ****kwargs** – Constant values to pass to every agent’s constructor. Only non-sequence data is allowed in kwargs to avoid ambiguity with DataFrame columns.

**Returns:**

AgentSet containing the agents created.

Note

If you need to pass variable data or sequences, add them as columns to the DataFrame before calling this method.

#### `property random: Random`

the model’s, or the agent’s own with agent_streams.

**Type:**

Return a seeded stdlib rng

#### `property rng: Generator`

the model’s, or the agent’s own with agent_streams.

**Type:**

Return a seeded np.random rng

#### `stream_key() → int`

Key of the agent’s own streams (`agent_streams`): `unique_id` unless overridden.

#### `property scenario`

Return the scenario associated with the model.

## Agent sets

`AgentSet` takes its selection methods (`select`, `select_random`) from `modelly.core.agentset.selection` and its attribute methods (`get`, `set`, `agg`) from `modelly.core.agentset.attributes`; they are listed under `AgentSet`.

AgentSet: the weak-reference ordered set every view is made of.

#### `class AgentSet(agents: Iterable[A], random: Random | None = None)`

Bases: [`AbstractAgentSet`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agentset.abstract.AbstractAgentSet), [`Generic`](https://docs.python.org/3/library/typing.html#typing.Generic)

A collection class that represents an ordered set of agents using weak references.

This implementation uses weak references to agents, allowing for efficient management of agent lifecycles without preventing garbage collection.

**Variables:**

**random** (*Random*) – The random number generator for this agent set.

Notes

The AgentSet maintains weak references to agents, which means that agents not referenced elsewhere in the program may be automatically removed from the AgentSet. This is the default implementation for most use cases where automatic cleanup is desired.

Internally the set is a plain `dict` keyed on `weakref.ref` objects (a `weakref.ref` hashes and compares like its referent while that is alive), which is about twice as fast as `weakref.WeakKeyDictionary` for construction, membership and iteration because it skips that class’s pure-Python wrapper and iteration guard. Each ref carries a callback that drops the entry when its agent is garbage collected. All bulk operations walk a snapshot of the keys, never the live dict, so a callback or user code mutating the set mid-iteration is always safe.

Initialize the AgentSet with weak references to agents.

**Parameters:**

- **agents** (*Iterable**[*[*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)*]*) – An iterable of Agent objects to be included in the set.
- **random** (*Random** | **None*) – The random number generator for this agent set.

#### `to_list() → list[A]`

Convert the AgentSet to a list.

**Returns:**

A list containing all agents in the AgentSet.

**Return type:**

[list](https://docs.python.org/3/builtins/stdtypes.html#list)[[Agent](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)]

Notes

Use this when you need list operations such as indexing or slicing; an AgentSet is an ordered set, not a sequence.

#### `add(agent: A)`

Add an agent to the AgentSet.

**Parameters:**

**agent** ([*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)) – The agent to add to the set.

Note

This method is an implementation of the abstract method from MutableSet.

#### `discard(agent: A)`

Remove an agent from the AgentSet if it exists.

This method does not raise an error if the agent is not present.

**Parameters:**

**agent** ([*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)) – The agent to remove from the set.

Note

This method is an implementation of the abstract method from MutableSet.

#### `remove(agent: A)`

Remove an agent from the AgentSet.

This method raises an error if the agent is not present.

**Parameters:**

**agent** ([*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)) – The agent to remove from the set.

Note

This method is an implementation of the abstract method from MutableSet.

#### `shuffle(inplace: bool = False) → AgentSet[A]`

Randomly shuffle the order of agents (see `AbstractAgentSet.shuffle`).

In place, the set’s own weakrefs are reordered rather than rebuilt: the same live agents are shuffled with the same draws, in the same order.

#### `do(method: str | Callable, *args, **kwargs) → AgentSet[A]`

Invoke a method or function on each agent in the AgentSet.

**Parameters:**

- **method** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **callable*) –
the callable to do on each agent
- in case of str, the name of the method to call on each agent.
- in case of callable, the function to be called with each agent as first argument
- ***args** – Variable length argument list passed to the callable being called.
- ****kwargs** – Arbitrary keyword arguments passed to the callable being called.

**Returns:**

The AgentSet instance itself.

**Return type:**

[AgentSet](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agentset.weak.AgentSet)

#### `shuffle_do(method: str | Callable, *args, **kwargs) → AgentSet[A]`

Shuffle the agents in the AgentSet and then invoke a method or function on each agent.

It’s a fast, optimized version of calling shuffle() followed by do().

#### `map(method: str | Callable, *args, **kwargs) → list[Any]`

Invoke a method or function on each agent in the AgentSet and return the results.

**Parameters:**

- **method** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **callable*) –
the callable to apply on each agent
- in case of str, the name of the method to call on each agent.
- in case of callable, the function to be called with each agent as first argument
- ***args** – Variable length argument list passed to the callable being called.
- ****kwargs** – Arbitrary keyword arguments passed to the callable being called.

**Returns:**

The results of the callable calls

**Return type:**

[list](https://docs.python.org/3/builtins/stdtypes.html#list)[Any]

#### `agg(attribute: str, func: Callable | Iterable[Callable]) → Any | list[Any]`

Aggregate an attribute of all agents in the AgentSet using one or more functions.

**Parameters:**

- **attribute** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The name of the attribute to aggregate.
- **func** (*Callable** | **Iterable**[**Callable**]*) –
- If Callable: A single function to apply to the attribute values (e.g., min, max, sum, np.mean)
- If Iterable: Multiple functions to apply to the attribute values

**Returns:**

Result of applying the function(s) to the attribute values.

**Return type:**

Any | [Any, …]

Examples

# Single function avg_energy = model.agents.agg(“energy”, np.mean)

# Multiple functions min_wealth, max_wealth, total_wealth = model.agents.agg(“wealth”, [min, max, sum])

#### `clear()`

This is slow (creates N new iterators!) but effective.

#### `get(attr_names, handle_missing='error', default_value=None)`

Retrieve the specified attribute(s) from each agent in the AgentSet.

**Parameters:**

- **attr_names** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | *[*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]*) – The name(s) of the attribute(s) to retrieve from each agent.
- **handle_missing** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **optional*) – How to handle missing attributes. Can be: - ‘error’ (default): raises an AttributeError if attribute is missing. - ‘default’: returns the specified default_value.
- **default_value** (*Any**, **optional*) – The default value to return if ‘handle_missing’ is set to ‘default’ and the agent does not have the attribute.

**Returns:**

A list with the attribute value for each agent if attr_names is a str. list[list[Any]]: A list with a lists of attribute values for each agent if attr_names is a list of str.

**Return type:**

[list](https://docs.python.org/3/builtins/stdtypes.html#list)[Any]

**Raises:**

- [**AttributeError**](https://docs.python.org/3/builtins/exceptions.html#AttributeError) – If ‘handle_missing’ is ‘error’ and the agent does not have the specified attribute(s).
- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If an unknown ‘handle_missing’ option is provided.

#### `groupby(by: Callable | str, result_type: Literal['agentset', 'list'] = 'agentset') → GroupBy`

Group agents by the specified attribute or return from the callable.

**Parameters:**

- **by** (*Callable**, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) –
used to determine what to group agents by
- if `by` is a callable, it will be called for each agent and the return is used for grouping
- if `by` is a str, it should refer to an attribute on the agent and the value of this attribute will be used for grouping
- **result_type** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **optional*) – The datatype for the resulting groups {“agentset”, “list”}

**Returns:**

GroupBy

Notes

There might be performance benefits to using result_type=’list’ if you don’t need the advanced functionality of an AbstractAgentSet.

#### `isdisjoint(other)`

Return True if two sets have a null intersection.

#### `pop()`

Return the popped value. Raise KeyError if empty.

#### `select(filter_func: Callable[[A], bool] | None = None, at_most: int | float = inf, inplace: bool = False, agent_type: type[A] | None = None) → AbstractAgentSet[A]`

Select a subset of agents from the AbstractAgentSet based on a filter function and/or quantity limit.

**Parameters:**

- **filter_func** (*Callable**[**[*[*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)*]**, *[*bool*](https://docs.python.org/3/builtins/functions.html#bool)*]**, **optional*) – A function that takes an Agent and returns True if the agent should be included in the result. Defaults to None, meaning no filtering is applied.
- **at_most** ([*int*](https://docs.python.org/3/builtins/functions.html#int)* | *[*float*](https://docs.python.org/3/builtins/functions.html#float)*, **optional*) – The maximum amount of agents to select. Defaults to infinity. - If an integer, at most the first number of matching agents are selected. - If a float between 0 and 1, at most that fraction of original the agents are selected.
- **inplace** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)*, **optional*) – If True, modifies the current AbstractAgentSet; otherwise, returns a new AbstractAgentSet. Defaults to False.
- **agent_type** ([*type*](https://docs.python.org/3/builtins/functions.html#type)*[*[*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)*]**, **optional*) – The class type of the agents to select. Defaults to None, meaning no type filtering is applied.

**Returns:**

A new AbstractAgentSet containing the selected agents, unless inplace is True, in which case the current AbstractAgentSet is updated.

**Return type:**

[AbstractAgentSet](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agentset.abstract.AbstractAgentSet)

**Raises:**

- [**TypeError**](https://docs.python.org/3/builtins/exceptions.html#TypeError) – If at_most is not an integer or float, or is a boolean.
- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If at_most is a negative integer, or a float not in the range (0.0, 1.0].

Notes

- at_most just return the first n or fraction of agents. To take a random sample, shuffle() beforehand.
- at_most is an upper limit. When specifying other criteria, the number of agents returned can be smaller.

#### `select_random(n: int | float = 1, *, weights: str | Callable[[A], float] | Sequence[float] | None = None, replace: bool = False, inplace: bool = False) → AbstractAgentSet[A]`

Select a random or weighted sample of agents from the AbstractAgentSet.

**Parameters:**

- **n** ([*int*](https://docs.python.org/3/builtins/functions.html#int)* | *[*float*](https://docs.python.org/3/builtins/functions.html#float)*, **optional*) – The number or fraction of agents to select. Defaults to 1. - If an integer >= 1, the number of agents to select. - If a float in (0, 1], the fraction of agents to select.
- **weights** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **Callable**[**[*[*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)*]**, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*] **| **Sequence**[*[*float*](https://docs.python.org/3/builtins/functions.html#float)*] **| **None**, **optional*) – Weights for selection. - If a str: uses the specified agent attribute name. - If a Callable: calls the function on each agent to compute its weight. - If a Sequence: a sequence of numerical weights of the same length as the AgentSet. - If None: uniform random selection. Defaults to None.
- **replace** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)*, **optional*) – Whether to sample with replacement. Defaults to False.
- **inplace** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)*, **optional*) – If True, modifies the current AbstractAgentSet; otherwise, returns a new AbstractAgentSet. Defaults to False.

**Returns:**

A new or updated AbstractAgentSet containing the sampled agents.

**Return type:**

[AbstractAgentSet](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agentset.abstract.AbstractAgentSet)

**Raises:**

- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If the AgentSet is empty, n <= 0, n > len(self) when replace=False, n exceeds the number of positive weights when sampling without replacement, weights are negative, total weight <= 0, or length of weights sequence does not match the AgentSet.
- [**TypeError**](https://docs.python.org/3/builtins/exceptions.html#TypeError) – If n or weights is of an unsupported type.

#### `set(attr_name: str, value: Any) → AgentSet[A]`

Set a specified attribute for the agents in the AgentSet.

The behavior is derived from `value` (the same value-based rule pandas uses for column assignment):

- A `list`, `tuple`, `numpy.ndarray` or `pandas.Series` is treated as one value per agent and is assigned element-wise, in iteration order (the same order `get` uses), so a `get -> transform -> set` round-trip stays consistent. It must have the same length as the AgentSet; a length mismatch raises `ValueError`.
- Any other value (a scalar, a string, or any non-sequence) is broadcast: every agent receives the same value.

**Parameters:**

- **attr_name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The name of the attribute to set.
- **value** (*Any*) – The value(s) to assign. See above for how the shape of `value` selects element-wise vs broadcast assignment.

**Returns:**

The AgentSet instance itself, after setting the attribute.

**Return type:**

[AgentSet](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agentset.weak.AgentSet)

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If `value` is a sequence whose length does not match the number of agents in the AgentSet.

Notes

A per-agent sequence is recognized by its type (list, tuple, ndarray, Series). To assign a single sequence value to every agent, broadcast it explicitly, e.g. `[shared_list] * len(agentset)`.

#### `sort(key: Callable[[A], Any] | str, ascending: bool = False, inplace: bool = False) → AbstractAgentSet[A]`

Sort the agents in the AbstractAgentSet based on a specified attribute or custom function.

**Parameters:**

- **key** (*Callable**[**[*[*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)*]**, **Any**] **| *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – A function or attribute name based on which the agents are sorted.
- **ascending** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)*, **optional*) – If True, the agents are sorted in ascending order. Defaults to False.
- **inplace** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)*, **optional*) – If True, sorts the agents in the current set; otherwise, returns a new sorted AgentSet. Defaults to False.

**Returns:**

A sorted set. Returns the current set if inplace is True.

The interface and shared algorithms of every agent set.

#### `class AbstractAgentSet`

Bases: `SelectionMixin`, `AttributeMixin`, [`ABC`](https://docs.python.org/3/library/abc.html#abc.ABC), [`MutableSet`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableSet), [`Generic`](https://docs.python.org/3/library/typing.html#typing.Generic)

An abstract base collection class that represents an ordered set of agents within an agent-based model (ABM).

This class defines the minimal interface that all AgentSet implementations must follow. Subclasses are free to override methods with optimized implementations based on their storage mechanism (weak references vs strong references).

**Variables:**

**model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The ABM model instance to which this AbstractAgentSet belongs.

#### `abstractmethod to_list() → list[A]`

Convert the AbstractAgentSet to a list.

**Returns:**

A list containing all agents in the AbstractAgentSet.

**Return type:**

[list](https://docs.python.org/3/builtins/stdtypes.html#list)[[Agent](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)]

Notes

Use this when you need list operations such as indexing or slicing; an AgentSet is an ordered set, not a sequence.

#### `abstractmethod add(agent: A)`

Add an agent to the AbstractAgentSet.

**Parameters:**

**agent** ([*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)) – The agent to add to the set.

Note

This method is an implementation of the abstract method from MutableSet.

#### `abstractmethod discard(agent: A)`

Remove an agent from the AbstractAgentSet if it exists.

This method does not raise an error if the agent is not present.

**Parameters:**

**agent** ([*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)) – The agent to remove from the set.

Note

This method is an implementation of the abstract method from MutableSet.

#### `abstractmethod remove(agent: A)`

Remove an agent from the AbstractAgentSet.

**Raises:**

**An Exception if the agent is not present.** –

**Parameters:**

**agent** ([*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)) – The agent to remove from the set.

Note

This method is an implementation of the abstract method from MutableSet.

#### `groupby(by: Callable | str, result_type: Literal['agentset', 'list'] = 'agentset') → GroupBy`

Group agents by the specified attribute or return from the callable.

**Parameters:**

- **by** (*Callable**, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) –
used to determine what to group agents by
- if `by` is a callable, it will be called for each agent and the return is used for grouping
- if `by` is a str, it should refer to an attribute on the agent and the value of this attribute will be used for grouping
- **result_type** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **optional*) – The datatype for the resulting groups {“agentset”, “list”}

**Returns:**

GroupBy

Notes

There might be performance benefits to using result_type=’list’ if you don’t need the advanced functionality of an AbstractAgentSet.

#### `shuffle(inplace: bool = False) → AbstractAgentSet[A]`

Randomly shuffle the order of agents in the AbstractAgentSet.

**Parameters:**

**inplace** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)*, **optional*) – If True, shuffles the agents in the current set; otherwise, returns a new shuffled AgentSet. Defaults to False.

**Returns:**

A shuffled set. Returns the current set if inplace is True.

Note

Using inplace = True is more performant

#### `sort(key: Callable[[A], Any] | str, ascending: bool = False, inplace: bool = False) → AbstractAgentSet[A]`

Sort the agents in the AbstractAgentSet based on a specified attribute or custom function.

**Parameters:**

- **key** (*Callable**[**[*[*Agent*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.agent.Agent)*]**, **Any**] **| *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – A function or attribute name based on which the agents are sorted.
- **ascending** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)*, **optional*) – If True, the agents are sorted in ascending order. Defaults to False.
- **inplace** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)*, **optional*) – If True, sorts the agents in the current set; otherwise, returns a new sorted AgentSet. Defaults to False.

**Returns:**

A sorted set. Returns the current set if inplace is True.

#### `abstractmethod do(method: str | Callable, *args, **kwargs) → AbstractAgentSet[A]`

Invoke a method or function on each agent in the AbstractAgentSet.

#### `abstractmethod shuffle_do(method: str | Callable, *args, **kwargs) → AbstractAgentSet[A]`

Shuffle the agents in the AbstractAgentSet and then invoke a method or function on each agent.

#### `abstractmethod map(method: str | Callable, *args, **kwargs) → list[Any]`

Invoke a method or function on each agent in the AbstractAgentSet and return the results.

GroupBy: the result of AgentSet.groupby.

#### `class GroupBy(groups: dict[Any, list | AbstractAgentSet])`

Helper class for AgentSet.groupby.

**Variables:**

**groups** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)) – A dictionary with the group_name as key and group as values

Initialize a GroupBy instance.

**Parameters:**

**groups** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)) – A dictionary with the group_name as key and group as values

#### `get_group(name: Hashable, default: Any = <object object>) → list | AbstractAgentSet | Any`

Return the group for the given name.

**Parameters:**

- **name** (*Hashable*) – The group name to retrieve.
- **default** (*Any**, **optional*) – Value to return when the group is missing.

**Raises:**

[**KeyError**](https://docs.python.org/3/builtins/exceptions.html#KeyError) – If the group does not exist and no default is provided.

#### `map(method: Callable | str, *args, **kwargs) → dict[Any, Any]`

Apply the specified callable to each group and return the results.

**Parameters:**

- **method** (*Callable**, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) –
The callable to apply to each group,
- if `method` is a callable, it will be called it will be called with the group as first argument
- if `method` is a str, it should refer to a method on the group
Additional arguments and keyword arguments will be passed on to the callable.
- **args** – arguments to pass to the callable
- **kwargs** – keyword arguments to pass to the callable

**Returns:**

dict with group_name as key and the return of the method as value

Notes

this method is useful for methods or functions that do return something. It will break method chaining. For that, use `do` instead.

#### `do(method: Callable | str, *args, **kwargs) → GroupBy`

Apply the specified callable to each group.

**Parameters:**

- **method** (*Callable**, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) –
The callable to apply to each group,
- if `method` is a callable, it will be called it will be called with the group as first argument
- if `method` is a str, it should refer to a method on the group
Additional arguments and keyword arguments will be passed on to the callable.
- **args** – arguments to pass to the callable
- **kwargs** – keyword arguments to pass to the callable

**Returns:**

the original GroupBy instance

Notes

this method is useful for methods or functions that don’t return anything and/or if you want to chain multiple do calls

#### `count() → dict[Any, int]`

Return the count of agents in each group.

**Returns:**

A dictionary mapping group names to the number of agents in each group.

**Return type:**

[dict](https://docs.python.org/3/builtins/stdtypes.html#dict)

#### `agg(attr_name: str, func: Callable) → dict[Hashable, Any]`

Aggregate the values of a specific attribute across each group using the provided function.

**Parameters:**

- **attr_name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The name of the attribute to aggregate.
- **func** (*Callable*) – The function to apply (e.g., sum, min, max, mean).

**Returns:**

A dictionary mapping group names to the result of applying the aggregation function.

**Return type:**

[dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[Hashable, Any]

## Columns

Columnar agent state: declare a `Column` on an `Agent` subclass and that attribute lives in a model-owned numpy array, readable per agent and as a whole.

Columnar agent state: attributes stored in model-owned numpy arrays.

Declare a `Column` on an `Agent` subclass and that attribute lives in one numpy array per agent class instead of in each instance’s `__dict__`. The agent keeps working as an object (`agent.wealth` reads and writes its own row) while the model gets a zero-copy view of every agent’s value at once:

```default
class MoneyAgent(Agent):
    wealth = Column(int, default=1)

table = model.columns[MoneyAgent]
table.wealth.mean()                    # numpy, no Python loop
table.wealth[table.wealth > 10] -= 1   # bulk update, in place
rich = table.where(table.wealth > 10)  # an AgentSet
```

Rows are in insertion order; removing an agent moves the last row into the freed slot, so a view is valid until the next add or remove. Use columns for the attributes you aggregate, filter, record or update in bulk; a plain attribute is still the cheapest thing to read inside `step`. Each column is a fast property on the class (`modelly.core.column_access`).

#### `class Column(dtype: Any = <class 'float'>, default: Any = 0)`

Descriptor declaring an agent attribute stored in a model-owned array.

**Parameters:**

- **dtype** – numpy dtype of the column.
- **default** – value every new agent starts with.

Declare a column with its dtype and the default each new agent gets.

#### `class ColumnTable(specs: dict[str, Column], random: Random, rng: Generator, storage: InMemory = InMemory())`

The arrays of one agent class, one row per live agent.

Attribute access (`table.wealth`) and item access (`table["wealth"]`) return a view of the live rows. `table.unique_id` is always present.

Allocate one array per column plus the unique_id column, in `storage`.

#### `property columns: list[str]`

Column names, `unique_id` first.

#### `property agents: list[Agent]`

The agents in row order (a copy of the list).

#### `where(mask: ndarray) → AgentSet`

Return the agents whose row is True in `mask` as an AgentSet.

#### `draw(p: float | ndarray) → ndarray`

One Bernoulli draw per agent from the model’s seeded numpy generator.

`p` is a probability or one probability per row. The “reproduce with probability p” phase of a step is `table.do_where(table.draw(p), "spawn")`.

#### `do_where(mask: ndarray, method: str, *args, **kwargs) → int`

Call `method` on every agent whose row is True in `mask`; return how many.

The agents are snapshotted first, so the method may add or remove agents.

#### `remove_where(mask: ndarray) → int`

Remove every agent whose row is True in `mask`; return how many.

The “die” phase of a step: `table.remove_where(table.energy < 0)`. Each agent goes through `agent.remove()`, so spaces and datasets are updated.

#### `thin(name: str, survival: float | ndarray) → ndarray`

Replace the counts in column `name` by Binomial(count, survival) draws.

For a row of `count` identical individuals, each surviving independently with probability `survival`, the number left is Binomial(count, survival) (a sum of Bernoulli draws), so one draw per cohort has the individual model’s law. Returns the live-rows view of the column after the draw.

#### `to_dataframe() → DataFrame`

Copy the live rows into a DataFrame indexed by `unique_id`.

#### `add(agent: Agent) → int`

Append a row for `agent` (with the column defaults) and return it.

#### `remove(agent: Agent) → None`

Free `agent`’s row by moving the last row into it.

Per-agent access: on the class, each column is a property that reads the agent’s row through a `memoryview` (see `Agent.column_specs()` for the declarations).

Fast per-agent access to `Column` attributes.

A `Column` declared on an agent class is replaced on that class by a plain `property`: the interpreter inlines property getters, which a custom descriptor never gets. The getter reads the agent’s row through a `memoryview` of the column’s array, which returns a Python `int`, `float` or `bool` instead of building a numpy scalar, so the value is cheaper to read and much cheaper to do arithmetic on. Dtypes a `memoryview` cannot index (strings, objects, complex, datetimes) keep the numpy array.

Measured on CPython 3.15, one access inside a step:

plain attribute read 6 ns += 1 13 ns Column, descriptor read 79 ns += 1 171 ns Column, this module read 27 ns += 1 72 ns

#### `fast_view(array: ndarray) → Any`

A `memoryview` of `array` when it indexes to Python scalars, else `array`.

#### `column_property(name: str, position: int, column: Column) → property`

The property installed for column `name`, at `position` in the class’s specs.

#### `collect_column_specs(cls: type) → dict[str, Column]`

The columns of `cls`: inherited ones first, in MRO order, then its own.

Agent classes already processed keep their declarations in `_column_specs` (their attributes are properties by then); other bases, such as plain mixins, are scanned for `Column` instances.

#### `install_column_properties(cls: type, specs: dict[str, Column]) → None`

Replace every column of `cls` by its fast property.

## Random numbers

`model.random` is a `FastRandom`: a `random.Random` that gives exactly the standard library’s numbers for a seed, faster. When the compiled core is built for the interpreter (platform wheels for Linux and macOS, or `bash scripts/build-native.sh` in a checkout), `randint`, `choice`, `shuffle`, `sample` and `_randbelow` run in C on CPython’s own Mersenne Twister state; otherwise `FastRandom` is `PyFastRandom`, the pure-Python version. `modelly.core.rng.NATIVE` says which one is in use, and `MODELLY_PURE_PYTHON=1` forces the Python one.

A faster `random.Random` with the standard library’s exact streams.

`FastRandom` is a compiled core (`modelly._native.fastrng`, C on CPython’s own Mersenne Twister state) when it is built for this interpreter and passes a stream self-test at import, and the pure-Python `PyFastRandom` otherwise. `MODELLY_PURE_PYTHON=1` forces the Python version. Both give, for a seed, exactly the numbers `random.Random` gives.

`random.Random` implements `randint`, `choice`, `shuffle` and `sample` in Python, and each draw goes through `_randbelow` as a separate method call plus argument validation. In an agent-based model those four calls run millions of times per experiment. `FastRandom` reimplements them with the rejection loop written inline, making the same `getrandbits` calls in the same order, so for a given seed it produces exactly the same numbers as `random.Random`; a run seeded with either is reproducible with the other.

#### `class PyFastRandom(x=None)`

`random.Random` with the hot draws inlined in Python; identical streams.

The fallback for `FastRandom` where the compiled core is unavailable. Both versions pickle to the same state, so a pickle written with one loads into the other and continues the same stream.

Initialize an instance.

Optional argument x controls seeding, as for Random.seed().

#### `randint(a: int, b: int) → int`

Return a random integer in [a, b], like `random.randint`.

#### `choice(seq: Sequence[Any]) → Any`

Return a random element of `seq`, like `random.choice`.

#### `shuffle(x: MutableSequence[Any]) → None`

Shuffle `x` in place, like `random.shuffle` (same stream).

#### `sample(population: Sequence[Any], k: int, *, counts=None) → list`

Return `k` unique elements of `population`, like `random.sample`.

#### `class FastRandom(x=None)`

`random.Random` with its hot draws in C; identical streams.

`randint`, `choice`, `shuffle`, `sample` and `_randbelow` run in C on the same Mersenne Twister state as the rest of `random.Random`.

Initialize an instance.

Optional argument x controls seeding, as for Random.seed().

## Checkpoints

`Model.save`, `Model.load` and `Model.checkpoint_every` (listed under `Model`) write and read this format; see [Checkpoints](https://remipelloux.github.io/Modelly/dev/checkpoints.html).

Model checkpoints: save a run to one file and resume it bit for bit.

A checkpoint is a short text header followed by a pickle of the model:

```default
MODELLY-CHECKPOINT
{"format": 2, "modelly": "1.3.0", "python": "3.13", "compression": "gzip"}
<pickle, compressed or not>
```

The header is read without unpickling anything, so a file from another format, Modelly release or Python version is refused with a clear error before any of its bytes run.

Security: the payload is a pickle, and unpickling runs code chosen by whoever wrote the file. Only load checkpoints you created or otherwise trust.

#### `save_model(model: Model, path: str | Path, *, compress: bool = False) → None`

Write `model` to `path` as a checkpoint (see `Model.save()`).

The bytes go to a sibling temporary file first and `os.replace` moves it into place (atomic on every platform), so a reader never sees half a checkpoint.

#### `load_model(path: str | Path) → Model`

Read a checkpoint written by [`save_model()`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.checkpoint.save_model) (see `Model.load()`).

#### `class CheckpointWriter(model: Model, interval: float, path_pattern: str, compress: bool)`

Save the model every `interval` time units (see `Model.checkpoint_every()`).

Each save is a one-off LOW priority event that schedules the next one before writing, so the checkpoint itself holds the following save and a resumed run keeps checkpointing.

Schedule the first save `interval` time units from now.

#### `write() → None`

Schedule the next save, then save to `path_pattern.format(time=...)`.

#### `stop() → None`

Cancel the next save.

## Exceptions

Modelly-specific exception hierarchy.

#### `exception ModellyException`

Bases: [`Exception`](https://docs.python.org/3/builtins/exceptions.html#Exception)

Base class for all Modelly-specific exceptions.

#### `exception SpaceException`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.ModellyException)

Base exception for errors in the discrete_space module.

#### `agent_label(agent) → str`

`Sheep 12`: the agent’s class and unique_id, as a modeller names it.

#### `model_time(agent) → str`

`` at time 3.0``, or an empty string when the agent has no model.

#### `exception CellFullException(coordinate, agent=None)`

Bases: [`SpaceException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.SpaceException)

Raised when attempting to add an agent to a cell with no available capacity.

Initialize the exception.

**Parameters:**

- **coordinate** – The coordinate tuple of the full cell.
- **agent** – The agent moved there, named in the message when given.

#### `exception AgentMissingException(agent, coordinate)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.ModellyException)

Raised when attempting to remove an agent that is not in the cell.

Initialize the exception.

**Parameters:**

- **agent** – The agent instance that was expected.
- **coordinate** – The coordinate tuple of the cell.

#### `exception AgentRemovedError(agent, reason: str = 'it was already removed')`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.ModellyException), [`AttributeError`](https://docs.python.org/3/builtins/exceptions.html#AttributeError)

Raised when `remove()` is called on an agent that has left its space.

An `AttributeError`: the type these calls raised before the message named the agent.

Initialize the exception.

**Parameters:**

- **agent** – The agent `remove()` was called on.
- **reason** – Why there is nothing to remove.

#### `exception ColumnMissingError(agent, column: str)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.ModellyException), [`AttributeError`](https://docs.python.org/3/builtins/exceptions.html#AttributeError)

Raised when a Column attribute is used on an agent that has no row.

The agent was removed from its model (its row went with it), or its `__init__` never called `super().__init__(model)`. An `AttributeError`, as before.

Initialize the exception.

**Parameters:**

- **agent** – The agent whose column was read or written.
- **column** – The name of the Column attribute.

#### `exception CellMissingException(coordinate)`

Bases: [`SpaceException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.SpaceException)

Raised when attempting to access or remove a cell that does not exist.

Initialize the exception.

**Parameters:**

**coordinate** – The coordinate tuple of the missing cell.

#### `exception ConnectionMissingException(cell, other)`

Bases: [`SpaceException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.SpaceException)

Raised when attempting to disconnect a cell that is not connected.

Initialize the exception.

**Parameters:**

- **cell** – The source cell instance.
- **other** – The target cell instance that was not connected.

#### `exception TableMissingException(table_name)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.ModellyException), [`ValueError`](https://docs.python.org/3/builtins/exceptions.html#ValueError)

Raised when attempting to access a table that does not exist in the DataCollector.

Initialize the exception.

**Parameters:**

**table_name** – The name of the missing table.

#### `exception DimensionException(message)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.ModellyException), [`ValueError`](https://docs.python.org/3/builtins/exceptions.html#ValueError)

Raised when spatial dimensions do not match expectations or are invalid.

Initialize the exception.

**Parameters:**

**message** – The error message describing the dimension mismatch.

#### `exception CheckpointError`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.ModellyException)

Raised when a model cannot be saved to, or loaded from, a checkpoint.
