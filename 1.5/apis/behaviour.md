# Behaviour

`modelly.behaviour` holds building blocks for what agents do: timed actions, continuous states with thresholds, and meta-agents (agents made of other agents).

Module

Contents

modelly.behaviour.actions

Action, ActionState, HasActions

modelly.behaviour.states

ContinuousState, Threshold

modelly.behaviour.meta_agents

MetaAgents, MembershipView, MembershipEdge

## Actions

An action takes time, can be interrupted and resumed, and runs on the model’s event list. `Action` takes its progress properties and hooks (`progress`, `remaining_time`, `on_start`, `on_complete`, …) from `modelly.behaviour.actions.lifecycle`; they are listed under `Action`.

The Action class: something an agent does over time.

Lifecycle states, hooks and internal transitions live in `modelly.behaviour.actions.lifecycle`; the agent-side API is the HasActions mixin in `modelly.behaviour.actions.actions`.

#### `class Action(agent: Agent, duration: float | Callable[[Agent], float] = 1.0, *, name: str | None = None, priority: float | Callable[[Agent], float] = 0.0, interruptible: bool = True, start_requirements: Callable[[Agent], bool] | Iterable[Callable[[Agent], bool]] | None = None, completion_requirements: Callable[[Agent], bool] | Iterable[Callable[[Agent], bool]] | None = None)`

Something an agent does over time.

Actions have a duration, can be interrupted, and track their own lifecycle state. They integrate with Modelly’s event scheduler for completion timing.

Subclass and override on_start/on_complete/on_interrupt for complex behavior. All hooks default to doing nothing (pass).

**Variables:**

- **agent** – The agent performing this action.
- **model** – The model (shortcut for agent.model).
- **name** – Human-readable identifier. Defaults to the class name.
- **duration** – Time to complete. May be a callable(agent) -> float for state-dependent duration, resolved at start time.
- **priority** – Importance level. Higher = more important. May be a callable(agent) -> float, resolved once: at start, or earlier if HasActions.interrupt_for weighs it against a running action.
- **interruptible** – Whether higher-priority actions can preempt this.
- **start_requirements** – Predicates that must hold for the action to start.
- **completion_requirements** – Predicates that must hold for the effect to apply. Empty by default.
- **state** – Current lifecycle state (PENDING, ACTIVE, COMPLETED, INTERRUPTED, FAILED).
- **progress** – Time fraction completed, 0.0 to 1.0. Computed live while the action is active.

Notes

Actions hold a reference to their agent, mirroring how agents reference their model. This allows actions to query and modify agent state directly in their hooks.

Initialize an Action.

**Parameters:**

- **agent** – The agent that will perform this action.
- **duration** – Time to complete. Either a float or a callable that receives the agent and returns a float. Resolved when start() is called.
- **name** – Human-readable name. Defaults to the class name.
- **priority** – Importance level for interruption decisions. Either a float or a callable that receives the agent and returns a float. Resolved once, at start() or when interrupt_for first consults the agent’s should_interrupt with it.
- **interruptible** – If False, interrupt() will fail and return False.
- **start_requirements** – A single callable(agent) -> bool, or an iterable of them. All must hold for the action to start.
- **completion_requirements** – The same, checked instead when the action completes, gating the effect rather than the attempt.

**Raises:**

[**TypeError**](https://docs.python.org/3/builtins/exceptions.html#TypeError) – If the agent does not inherit from HasActions.

#### `property name: str`

Human-readable name. Returns the class name by default.

Can be set via __init__(name=…), per-instance assignment (`action.name = "dig"`), or overridden in subclasses.

#### `start() → Action`

Start executing this action (or resume from interruption).

On first start (PENDING): resolves callable duration/priority, starts from progress=0. On resume (INTERRUPTED): continues from existing progress with remaining duration.

If a requirement does not hold the action moves to FAILED instead, firing on_fail() rather than on_start() or on_resume(). Inspect state after starting rather than assuming the action is ACTIVE.

**Returns:**

Self, for chaining.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If the action is not in PENDING or INTERRUPTED state. A FAILED action cannot be restarted; create a new one.

#### `interrupt() → bool`

Interrupt this action.

Updates progress, fires on_interrupt with the time fraction, and cancels the scheduled completion event. The action moves to INTERRUPTED state and can be resumed later with start().

**Returns:**

True if the action was interrupted, False if it could not be interrupted (non-interruptible or not active).

#### `cancel() → bool`

Cancel this action, ignoring the interruptible flag.

Like interrupt(), but always succeeds for active actions and moves to INTERRUPTED state. The action can still be resumed if desired.

**Returns:**

True if the action was cancelled, False if not active.

#### `property elapsed_time: float`

Total time spent on this action so far (across all attempts).

#### `property has_failed: bool`

Whether a requirement did not hold, at start or at completion.

#### `property is_resumable: bool`

Whether this action can be resumed (interrupted, not completed).

#### `on_complete() → None`

Called when the action finishes normally.

Override to apply the action’s full effect (e.g., gaining energy, completing a transaction).

#### `on_fail() → None`

Called when a requirement does not hold.

Override to release anything the action reserved, or to record the attempt.

Notes

Check self.progress to tell the two failures apart: it is 1.0 when the action ran its full duration and only then found the requirement broken, and below 1.0 when the action never got to run this attempt.

#### `on_interrupt(progress: float) → None`

Called when the action is interrupted before completion.

Override to handle partial completion. The progress parameter is the raw time fraction (0.0 to 1.0), giving you full control over how partial work translates to partial effect.

**Parameters:**

**progress** – Fraction of duration completed (elapsed / duration).

Notes

Also called by cancel(). If you need to distinguish interruption from cancellation, check self.interruptible: a non-interruptible action that receives on_interrupt was necessarily cancelled, not interrupted.

#### `on_resume() → None`

Called when the action resumes after interruption.

Override to handle resumption differently from first start (e.g., logging “resumed” instead of “started”, skipping setup that shouldn’t happen twice).

Default implementation calls on_start().

#### `on_start() → None`

Called when the action starts executing for the first time.

Override for setup logic (e.g., logging, animation triggers, resource reservation). Not called on resume — see on_resume().

#### `property progress: float`

Time fraction completed, 0.0 to 1.0.

Computed live while the action is active. For interrupted or completed actions, returns the final progress value.

#### `property remaining_time: float`

Time remaining until completion.

Computed live while active. For interrupted actions, returns the time that would remain if resumed.

Action lifecycle: states, subclass hooks and the internal state transitions.

`ActionLifecycle` is the base of `modelly.behaviour.actions.Action`. It holds the progress properties, the overridable hooks (on_start, on_resume, on_complete, on_interrupt, on_fail) and the private transitions that every way of ending an action goes through.

#### `class ActionState(*values)`

Lifecycle state of an Action.

modelly.behaviour.actions: Timed, interruptible actions for Modelly agents.

An Action represents something an agent does over time. It integrates with Modelly’s event scheduling system for precise timing and supports interruption with progress tracking and optional resumption.

Actions are subclassable: override on_start(), on_complete(), on_interrupt(), and on_fail() to define behavior. The agent-side API lives on the HasActions mixin; when an action ends, the agent’s on_idle() hook fires, and decisions about what to do next – chain another action, resume an interrupted one – belong there.

Example:

```default
class Sheep(HasActions, Agent):
    pass

class Forage(Action):
    def __init__(self, sheep):
        super().__init__(sheep, duration=5.0)

    def on_complete(self):
        self.agent.energy += 30

    def on_interrupt(self, progress):
        self.agent.energy += 30 * progress

sheep.start_action(Forage(sheep))
```

#### `class HasActions(*args, **kwargs)`

Mixin that lets an agent perform Actions.

An agent performs at most one action at a time, held in `current_action`. Actions are started with start_action(), preempted through interrupt_for() under the should_interrupt() policy, and force-stopped with cancel_action(). Whenever an action ends and nothing replaces it, the on_idle() wake fires.

Action instances require their agent to inherit from this mixin.

Initialize the action slot.

#### `remove() → None`

Remove the agent, abandoning its action and pending wake.

If the agent is currently performing an action, the action’s scheduled completion event is cancelled silently. The action’s on_interrupt() callback is NOT fired, because the agent is being destroyed — not making a behavioral decision. The action moves to no defined end state; it is simply abandoned. A pending on_idle wake is cancelled as well: a removed agent never wakes.

If your action holds external resources (e.g., a Resource slot, a reservation, a lock), override remove() and call self.cancel_action() before super().remove() to ensure on_interrupt() fires and cleanup logic runs:

**def remove(self):**

self.cancel_action() # Fires on_interrupt for cleanup super().remove()

Notes

This is a deliberate design choice. The default silent cleanup is safe and avoids callbacks touching agent state during teardown. Models that need cleanup should opt in explicitly.

#### `start_action(action: Action) → Action`

Start performing an action.

The action must be in PENDING or INTERRUPTED state and the agent must not be currently performing another action.

If one of the action’s start requirements does not hold, the action moves to FAILED instead of starting and the agent stays idle. Check action.has_failed rather than assuming the action is running.

**Parameters:**

**action** – The Action to perform. Must have been created with this agent as its agent.

**Returns:**

The started Action.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If the agent is already performing an action, or if the action doesn’t belong to this agent.

#### `should_interrupt(current: Action, incoming: Action) → bool`

Decide whether an incoming action may preempt the current one.

Consulted by interrupt_for() whenever the agent is busy, with both priorities already resolved. Override to encode preemption policy, e.g. comparing action names or agent state instead of priorities.

**Parameters:**

- **current** – The action the agent is performing.
- **incoming** – The action that wants to replace it.

**Returns:**

True to attempt the interruption, False to refuse it.

Notes

Returning True cannot override the interruptible flag; use cancel_action() to force. This hook decides policy, the flag stays a hard property of the action.

#### `interrupt_for(new_action: Action) → bool`

Interrupt the current action and start a new one.

If there is no current action, simply starts the new one. Otherwise should_interrupt(current, incoming) decides whether to preempt.

**Parameters:**

**new_action** – The Action to perform instead.

**Returns:**

True if the new action was started. False if should_interrupt refused, the current action is non-interruptible, or the new action failed its start requirements.

Notes

The False cases differ in what they leave behind. A refusal changes nothing. A failed requirement does not roll the interruption back: the old action is already INTERRUPTED and the agent is left idle, since whether to resume it is the model’s decision.

#### `cancel_action() → bool`

Cancel the current action, ignoring interruptible flag.

Calls on_interrupt with partial progress. Returns False only if there is no current action.

**Returns:**

True if an action was cancelled, False if idle.

#### `property is_busy: bool`

Whether the agent is currently performing an action.

#### `on_idle(previous: Action | None) → None`

Called when the agent’s action has ended and nothing replaced it.

Fires for every way an action can end – completion, interruption, cancellation, failure – as a zero-delay `Priority.LOW` event rather than synchronously, so every agent finishing at time t decides after all completions at t have run.

Override it to choose what to do next, typically by starting or resuming an action. The default does nothing, and nothing is resumed automatically: an interrupted action stays interrupted unless this hook (or other model code) restarts it.

**Parameters:**

**previous** – The action that just ended, in its final state (COMPLETED, INTERRUPTED, or FAILED). None is reserved for wakes not caused by an action ending; no built-in trigger sends it today.

Notes

At most one wake fires per agent per model time, so a zero-duration action started here cannot re-trigger the hook in the same instant; a wake dropped by this guard is logged at DEBUG level. The wake is skipped when the agent is busy again by the time the event runs – interrupt_for() refills the slot synchronously, so no idle gap ever existed. If several actions end before the wake runs, they coalesce into one call and `previous` is the latest of them.

## States

Continuous States Descriptor.

Provides piecewise-linear and piecewise-quadratic trajectory tracking, and declarative threshold monitors natively integrated with signals and the standard Modelly event queue.

#### `class ContinuousState(fallback_value: float = 0.0, rate: float | Callable[[Any], float] = 0.0)`

Bases: [`BaseObservable`](https://remipelloux.github.io/Modelly/apis/time.html#modelly.time.signals.core.BaseObservable)

A descriptor that tracks and extrapolates continuous states over time.

Uses piecewise-linear interpolation by default: value(t) = base_value + current_rate * (t - last_time). When the rate changes, the current value is snapshotted as the new baseline so the trajectory remains mathematically continuous.

Chained states (e.g. position’ = speed, where speed is itself a ContinuousState) are extrapolated with the next order term instead: value(t) = base_value + current_rate*dt + 0.5*second_order_rate*dt**2.

Initialize a ContinuousState.

**Parameters:**

- **fallback_value** – Initial value for the state (default 0.0).
- **rate** – Either a constant float rate-of-change, or a callable f(agent) -> float that is evaluated reactively via the diffing engine.

#### `signal_types`

alias of [`ObservableSignals`](https://remipelloux.github.io/Modelly/apis/time.html#modelly.time.signals.types.ObservableSignals)

#### `get_rate(instance: HasEmitters) → float`

Return the current rate for the instance, evaluating lazily if needed.

**Parameters:**

**instance** ([*HasEmitters*](https://remipelloux.github.io/Modelly/apis/time.html#modelly.time.signals.emitters.HasEmitters)) – The instance being evaluated.

**Returns:**

The currently active rate.

**Return type:**

[float](https://docs.python.org/3/builtins/functions.html#float)

#### `class Threshold(state: ContinuousState, limit: float | Observable, callback: str, direction: str = 'crossing')`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Class-level descriptor that fires a callback when a ContinuousState crosses a limit.

The limit may be a fixed float or an Observable attribute on the agent. When the limit is an Observable, the threshold recalculates automatically whenever the limit changes – no imperative re-arming calls needed.

Initialize the Threshold descriptor.

**Parameters:**

- **state** – The ContinuousState descriptor to monitor.
- **limit** – The crossing value, either a fixed float or an Observable on the agent. When an Observable, the projected crossing time updates automatically whenever the limit changes.
- **callback** – Name of the agent method to call when the limit is crossed.
- **direction** – The boundary direction constraint (“rising”, “falling”, or “crossing”).

#### `bind(instance: Agent) → None`

Wire up this threshold for the instance via the signal bus.

Subscribes to CHANGED signals from both the watched ContinuousState and, when the limit is an Observable, from the limit itself – so the projected crossing time updates automatically whenever either changes.

**Parameters:**

**instance** ([*Agent*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.agent.Agent)) – The instance to bind to.

#### `recalculate(instance: Agent) → None`

Compute and cache the exact crossing time using quadratic extrapolation.

Solves the intersection root using 0.5*a*t^2 + v*t + (x0 - limit) = 0.

#### `execute(instance: Agent) → None`

Fire the callback when a crossing is reached.

**Parameters:**

**instance** ([*Agent*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.agent.Agent)) – The instance whose threshold was triggered.

Threshold descriptor: fire a callback when a ContinuousState crosses a limit.

#### `class Threshold(state: ContinuousState, limit: float | Observable, callback: str, direction: str = 'crossing')`

Class-level descriptor that fires a callback when a ContinuousState crosses a limit.

The limit may be a fixed float or an Observable attribute on the agent. When the limit is an Observable, the threshold recalculates automatically whenever the limit changes – no imperative re-arming calls needed.

Initialize the Threshold descriptor.

**Parameters:**

- **state** – The ContinuousState descriptor to monitor.
- **limit** – The crossing value, either a fixed float or an Observable on the agent. When an Observable, the projected crossing time updates automatically whenever the limit changes.
- **callback** – Name of the agent method to call when the limit is crossed.
- **direction** – The boundary direction constraint (“rising”, “falling”, or “crossing”).

#### `bind(instance: Agent) → None`

Wire up this threshold for the instance via the signal bus.

Subscribes to CHANGED signals from both the watched ContinuousState and, when the limit is an Observable, from the limit itself – so the projected crossing time updates automatically whenever either changes.

**Parameters:**

**instance** ([*Agent*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.agent.Agent)) – The instance to bind to.

#### `recalculate(instance: Agent) → None`

Compute and cache the exact crossing time using quadratic extrapolation.

Solves the intersection root using 0.5*a*t^2 + v*t + (x0 - limit) = 0.

#### `execute(instance: Agent) → None`

Fire the callback when a crossing is reached.

**Parameters:**

**instance** ([*Agent*](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.agent.Agent)) – The instance whose threshold was triggered.

## Meta-agents

Meta-agents are agents composed of other agents, allowing you to build models with emergent, multi-level complexity. A built-in membership manager tracks the network edges and nested relationships between all agents.

To aid in the development of complex simulations, the meta-agent module includes features for intuitive use, management, and exploration:

- create groups of agents
- add and remove members
- look up who belongs to a group and which groups an agent belongs to
- walk nested levels (`at_level`)
- deactivate or dissolve a group
- find candidate groups (`find_combinations`), with cached scoring (`cache_build`)

```default
        model.meta_agents
       (membership manager)
                |
   create, add_member, remove_member
                |
     memberships (agent → group)
                |
  members_of / groups_of / at_level
                |
         deactivate / dissolve
```

Install the membership manager on the model, then create groups and change memberships only through `model.meta_agents`.

```python
from modelly import Agent, Model
from modelly.behaviour.meta_agents import MetaAgents

model = Model()
model.meta_agents = MetaAgents(model)

alice = Agent(model)
bob = Agent(model)
team = model.meta_agents.create("Team", [alice, bob])  # create a group of agents

model.meta_agents.add_member("Team", Agent(model))  # add members
model.meta_agents.members_of("Team")  # who belongs to a group
model.meta_agents.groups_of(alice)  # which groups an agent belongs to
model.meta_agents.query_memberships(alice)  # full membership snapshot for one entity
model.meta_agents.at_level(1, root=team)  # walk nested levels
model.meta_agents.dissolve(team)  # dissolve a group
model.meta_agents.find_combinations(
    [alice, bob], evaluation_func=score
)  # candidate groups
```

### Group creation and reuse

Groups are identified by their class name. `create` reuses an existing group only when at least one of the given agents already belongs to a group with that class name; the given agents are then added to it. Otherwise a new group is created. Calling `create` again with the same name but no overlapping members therefore creates a second, distinct group with the same name (which makes name-based lookups such as `members_of("Team")` ambiguous). To force a new group, use a unique class name (e.g., append a timestamp or UUID).

The group agent defaults to a plain `Agent` subclass; pass `modelly_agent_type` to base it on a custom `Agent` subclass instead.

```python
team = model.meta_agents.create("Team", [alice, bob])

# reuse: alice is already in the group, so carol is added to the same team
team2 = model.meta_agents.create("Team", [carol, alice])
assert team is team2

# more explicit alternative:
model.meta_agents.add_member("Team", carol)

# same name, no overlapping members -> a second, distinct group
other_team = model.meta_agents.create("Team", [dave])
assert other_team is not team

# unique names force distinct groups
team_a = model.meta_agents.create("Team_2026_A", [alice])
team_b = model.meta_agents.create("Team_2026_B", [dave])
```

### Caching candidate scores

Models that search the same agents for alliances every step re-score every candidate group on each `find_combinations` call. Wrap the scoring function once with `cache_build` and pass the wrapper instead: each group is scored the first time it is seen and served from the cache afterwards. Results and their order are unchanged, provided the scoring function is deterministic for a given group.

```python
class Alliances(Model):
    def __init__(self):
        super().__init__()
        self.meta_agents = MetaAgents(self)
        self.score = self.meta_agents.cache_build(shapley_value)  # build once

    def step(self):
        candidates = self.meta_agents.find_combinations(
            self.agents, size=2, evaluation_func=self.score
        )
```

The cache is keyed by the exact tuple of agents passed to the scoring function, so pass agents in a stable order (for example sorted by `unique_id`) to get hits. It never expires by itself: call `self.score.invalidate(agent)` when an agent’s state changes or it leaves the model (its groups are re-scored next time), or `self.score.invalidate()` to drop everything. `maxsize` bounds the cache, evicting the oldest score first; `score.hits` and `score.misses` show how well it works.

Removing an agent or group (`deactivate`, `dissolve`, or `agent.remove()`) costs time proportional to that entity’s own memberships, not to the total number of memberships in the model.

### Reference

`MetaAgents` takes its lookups (`members_of`, `groups_of`, `query_memberships`, `at_level`) from `modelly.behaviour.meta_agents.queries`; they are listed under `MetaAgents`.

Membership manager for meta-agents.

#### `class MembershipEdge(agent: Any, group: Any, relation: Hashable)`

A membership edge with live agent and group objects.

#### `class MembershipView(subject: Any, memberships: tuple[MembershipEdge, ...])`

Read-only snapshot of memberships for one entity.

#### `as_triplets() → set[tuple[Any, Any, Hashable]]`

Return the memberships as live-object triplets.

#### `property agents: set[Any]`

Return all unique agents referenced by the view.

#### `property groups: set[Any]`

Return all unique groups referenced by the view.

#### `property relations: set[Hashable]`

Return all unique relation labels referenced by the view.

#### `class MetaAgents(model: Any, backend: MembershipBackend | None = None)`

Membership manager for agents composed of other agents.

Tracks who belongs to which group. Change memberships with `create`, `add_member`, `remove_member`, `deactivate`, and `dissolve`. Removing an agent from the model also removes its memberships.

Create a membership manager bound to one model.

#### `create(new_agent_class: str, agents: ~collections.abc.Iterable[~typing.Any], modelly_agent_type: type[~modelly.core.agent.Agent] | None = <class 'modelly.core.agent.Agent'>, meta_attributes: dict[str, ~typing.Any] | None = None, meta_methods: dict[str, ~collections.abc.Callable] | None = None, relation: ~collections.abc.Hashable = 'member', memberships: ~collections.abc.Iterable[tuple[~typing.Any, ~collections.abc.Hashable]] | None = None) → MetaAgent`

Create a meta-agent group and record its memberships.

A group is identified by its class name, `new_agent_class`. When at least one of the given agents already belongs to an existing group whose class name matches `new_agent_class`, that group is reused: the given agents are added to it and the existing group object is returned. Otherwise a new group is created and registered as an agent on the model. Note that calling `create` with the same class name but no overlapping members therefore creates a second, distinct group with the same name; name-based lookups (e.g. `members_of("Team")`) then raise because the name is ambiguous. To force a new group, use a unique class name (e.g., append a timestamp or UUID). For an example see the alliance_formation model.

Duplicate members are removed, preserving the order of first appearance.

**Parameters:**

- **new_agent_class** – The group’s class name. A group with this name is reused if any of `agents` already belongs to it; otherwise a new group with this name is created.
- **agents** – Initial members of the group.
- **modelly_agent_type** – Modelly `Agent` class used as the base class of the group agent. Defaults to `Agent` when omitted. Ignored when an existing group is reused. Pass a custom `Agent` subclass to give the group its own behavior.
- **meta_attributes** – Attributes to set on the group. When a group is reused, these are set on the existing group.
- **meta_methods** – Methods to bind to the group. When a group is reused, these are bound to the existing group.
- **relation** – Membership relation label for `agents` (default `"member"`). Ignored when `memberships` is given.
- **memberships** – Alternative to `agents`; a list of `(member, relation)` tuples so each member can get its own relation label. When given, `agents` and `relation` are ignored.

**Returns:**

The group agent (newly created or existing).

Examples

Create a new team with two members (the group agent defaults to a plain `Agent` subclass):

```default
>>> team = model.meta_agents.create("Team", [alice, bob])
```

Add carol to the same team. Reuse requires at least one given agent to already be in the group, so include an existing member:

```default
>>> team2 = model.meta_agents.create("Team", [carol, alice])
>>> assert team is team2
```

This is the same as adding carol using `add_member` (more explicit):

```default
>>> model.meta_agents.add_member("Team", carol)
>>> assert carol in model.meta_agents.members_of("Team")
```

With the same class name but no overlapping members, a second, distinct group is created:

```default
>>> other_team = model.meta_agents.create("Team", [dave])
>>> assert other_team is not team
```

Force new groups by using unique names:

```default
>>> team_a = model.meta_agents.create("Team_2026_A", [...])
>>> team_b = model.meta_agents.create("Team_2026_B", [...])
```

#### `add_member(group: Hashable, member: Hashable, relation: Hashable = 'member') → MembershipView`

Add one member to one group.

#### `remove_member(group: Hashable, member: Hashable, relation: Hashable = 'member') → MembershipView`

Remove one member from one group.

#### `dissolve(entity: Hashable) → MembershipView`

Remove an entity’s memberships and delete it from the model when possible.

#### `deactivate(entity: Hashable) → MembershipView`

Remove an entity from all memberships without deleting the object.

#### `static cache_build(evaluation_func: Callable[[tuple[Agent, ...]], Any], maxsize: int | None = None) → CachedEvaluation`

Return a cached `evaluation_func` for repeated `find_combinations` calls.

Models that search the same agents for meta-agents every step otherwise re-score every candidate group each time. Build the cache once and pass it as `evaluation_func`; results and their order are unchanged as long as the wrapped function is deterministic for a given group.

**Parameters:**

- **evaluation_func** – Scores one candidate group, as for `find_combinations`.
- **maxsize** – Maximum number of cached scores; the oldest is evicted first. `None` (default) keeps every score.

**Returns:**

A callable `CachedEvaluation` with `hits`, `misses` and `invalidate()`.

Examples

```default
>>> score = model.meta_agents.cache_build(shapley_value)
>>> model.meta_agents.find_combinations(agents, size=2, evaluation_func=score)
>>> score.invalidate(departed_agent)  # its groups are re-scored next time
```

#### `static evaluate_combination(candidate_group: tuple[Agent, ...], evaluation_func: Callable[[tuple[Agent, ...]], float] | None) → tuple[tuple[Agent, ...], float] | None`

Evaluate a candidate meta-agent group with a user-supplied function.

#### `static find_combinations(group: Iterable, size: int | tuple[int, int] = (2, 5), evaluation_func: Callable[[tuple[Agent, ...]], float] | None = None, filter_func: Callable[[list[tuple[tuple[Agent, ...], float]]], list[tuple[tuple[Agent, ...], float]]] | None = None) → list[tuple[tuple[Agent, ...], float]]`

Find candidate agent groups and score them with `evaluation_func`.

The helper discovers potential meta-agents before creating them. It deliberately does not mutate model or membership state.

**Parameters:**

- **group** – The set of agents to find combinations in.
- **size** – The size or range of sizes for combinations. Defaults to (2, 5).
- **evaluation_func** – The function to evaluate combinations. Defaults to None.
- **filter_func** – Allows the user to specify how agents are filtered to form groups. Defaults to None.

**Returns:**

The list of valuable combinations, in a tuple first agentset of valuable combination and then the value of the combination.

**Return type:**

List

#### `at_level(level: int, *, root: Hashable, relation: RelationKey | None = 'member') → AgentSet`

Return agents at a containment depth below `root`.

Levels are structural shortest-path distances through membership edges, not a persistent `agent.level` property. `root` is level `0`; its direct members are level `1`. When an agent is reachable by more than one path, it appears only at its shallowest depth from `root`.

**Parameters:**

- **level** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Non-negative containment depth relative to `root`.
- **root** (*Hashable*) – Hierarchy root (live agent or unique id). Must be registered on this model’s membership manager.
- **relation** (RelationKey or None, default `"member"`) – Membership relation to traverse. `None` includes all relations.
- **Returns**
- **-------**
- **AgentSet** – Live agents at the requested level (empty if none).
- **Raises**
- **------**
- **ValueError** – If `level` is negative or `root` is not in the model.
- **Examples**
- **--------**
- **model.meta_agents.at_level****(****4** (*>>>*)
- **root=world****)**

#### `groups_of(agent: Hashable, relation: RelationKey | None = None) → AgentSet`

Return the live groups that contain one agent as an AgentSet.

#### `members_of(group: Hashable, relation: RelationKey | None = None) → AgentSet`

Return the live members of one group as an AgentSet.

#### `query_memberships(entity: Hashable, relation: RelationKey | None = None) → MembershipView`

Return a resolved, read-only snapshot of one entity’s memberships.

Read-only membership snapshots returned by the membership manager.

#### `class MembershipEdge(agent: Any, group: Any, relation: Hashable)`

A membership edge with live agent and group objects.

#### `class MembershipView(subject: Any, memberships: tuple[MembershipEdge, ...])`

Read-only snapshot of memberships for one entity.

#### `as_triplets() → set[tuple[Any, Any, Hashable]]`

Return the memberships as live-object triplets.

#### `property agents: set[Any]`

Return all unique agents referenced by the view.

#### `property groups: set[Any]`

Return all unique groups referenced by the view.

#### `property relations: set[Hashable]`

Return all unique relation labels referenced by the view.

Internal meta-agent group object.

Meta-agents are agents composed of other agents. Memberships are tracked by the model’s membership manager (`model.meta_agents`). This module holds the internal group `Agent` subclass.

#### `extract_class(agents_by_type: dict, new_agent_class: object) → type[Agent] | None`

Return the existing model agent class named `new_agent_class` if present.

Candidate meta-agent search: enumerate agent combinations and score them.

`evaluate_combination`, `find_combinations` and `cache_build` are exposed as static methods of `modelly.behaviour.meta_agents.MetaAgents`.

#### `evaluate_combination(candidate_group: tuple[Agent, ...], evaluation_func: Callable[[tuple[Agent, ...]], float] | None) → tuple[tuple[Agent, ...], float] | None`

Evaluate a candidate meta-agent group with a user-supplied function.

#### `find_combinations(group: Iterable, size: int | tuple[int, int] = (2, 5), evaluation_func: Callable[[tuple[Agent, ...]], float] | None = None, filter_func: Callable[[list[tuple[tuple[Agent, ...], float]]], list[tuple[tuple[Agent, ...], float]]] | None = None) → list[tuple[tuple[Agent, ...], float]]`

Find candidate agent groups and score them with `evaluation_func`.

The helper discovers potential meta-agents before creating them. It deliberately does not mutate model or membership state.

**Parameters:**

- **group** – The set of agents to find combinations in.
- **size** – The size or range of sizes for combinations. Defaults to (2, 5).
- **evaluation_func** – The function to evaluate combinations. Defaults to None.
- **filter_func** – Allows the user to specify how agents are filtered to form groups. Defaults to None.

**Returns:**

The list of valuable combinations, in a tuple first agentset of valuable combination and then the value of the combination.

**Return type:**

List

#### `class CachedEvaluation(evaluation_func: Callable[[tuple[Agent, ...]], Any], maxsize: int | None = None)`

Memoising wrapper around an `evaluation_func`; built by `cache_build`.

Scores are stored per candidate group, keyed by the exact tuple `find_combinations` passes in, so a repeated search over the same agents only calls the wrapped function for groups it has not seen. The cache never expires on its own: call [`invalidate()`](https://remipelloux.github.io/Modelly/apis/behaviour.html#modelly.behaviour.meta_agents.combinations.CachedEvaluation.invalidate) when the state a score depends on changes (for example when a member is removed or mutated).

Wrap `evaluation_func`; keep at most `maxsize` scores (no limit if None).

#### `invalidate(*agents: Agent) → int`

Drop the scores of groups containing any of `agents`; all if none given.

**Returns:**

The number of scores dropped.

#### `cache_build(evaluation_func: Callable[[tuple[Agent, ...]], Any], maxsize: int | None = None) → CachedEvaluation`

Return a cached `evaluation_func` for repeated `find_combinations` calls.

Models that search the same agents for meta-agents every step otherwise re-score every candidate group each time. Build the cache once and pass it as `evaluation_func`; results and their order are unchanged as long as the wrapped function is deterministic for a given group.

**Parameters:**

- **evaluation_func** – Scores one candidate group, as for `find_combinations`.
- **maxsize** – Maximum number of cached scores; the oldest is evicted first. `None` (default) keeps every score.

**Returns:**

A callable [`CachedEvaluation`](https://remipelloux.github.io/Modelly/apis/behaviour.html#modelly.behaviour.meta_agents.combinations.CachedEvaluation) with `hits`, `misses` and [`invalidate()`](https://remipelloux.github.io/Modelly/apis/behaviour.html#modelly.behaviour.meta_agents.combinations.CachedEvaluation.invalidate).

Examples

```default
>>> score = model.meta_agents.cache_build(shapley_value)
>>> model.meta_agents.find_combinations(agents, size=2, evaluation_func=score)
>>> score.invalidate(departed_agent)  # its groups are re-scored next time
```
