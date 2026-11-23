# Behaviour

`modelly.behaviour` holds building blocks for what agents do: timed actions, continuous states
with thresholds, and meta-agents (agents made of other agents).

| Module | Contents |
|---|---|
| `modelly.behaviour.actions` | `Action`, `ActionState`, `HasActions` |
| `modelly.behaviour.states` | `ContinuousState`, `Threshold` |
| `modelly.behaviour.meta_agents` | `MetaAgents`, `MembershipView`, `MembershipEdge` |

## Actions

An action takes time, can be interrupted and resumed, and runs on the model's event list.
`Action` takes its progress properties and hooks (`progress`, `remaining_time`, `on_start`,
`on_complete`, ...) from `modelly.behaviour.actions.lifecycle`; they are listed under `Action`.

```{eval-rst}
.. automodule:: modelly.behaviour.actions.action
   :members:
   :inherited-members:
```

```{eval-rst}
.. automodule:: modelly.behaviour.actions.lifecycle
   :members: ActionState
```

```{eval-rst}
.. automodule:: modelly.behaviour.actions.actions
   :members:
```

## States

```{eval-rst}
.. automodule:: modelly.behaviour.states.state
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.behaviour.states.threshold
   :members:
```

## Meta-agents

Meta-agents are agents composed of other agents, allowing you to build models
with emergent, multi-level complexity. A built-in membership manager tracks the
network edges and nested relationships between all agents.

To aid in the development of complex simulations, the meta-agent module
includes features for intuitive use, management, and exploration:

- create groups of agents
- add and remove members
- look up who belongs to a group and which groups an agent belongs to
- walk nested levels (`at_level`)
- deactivate or dissolve a group
- find candidate groups (`find_combinations`), with cached scoring (`cache_build`)

```
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

Install the membership manager on the model, then create groups and change
memberships only through `model.meta_agents`.

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

Groups are identified by their class name. `create` reuses an existing group
only when at least one of the given agents already belongs to a group with
that class name; the given agents are then added to it. Otherwise a new group
is created. Calling `create` again with the same name but no overlapping
members therefore creates a second, distinct group with the same name (which
makes name-based lookups such as `members_of("Team")` ambiguous). To force a
new group, use a unique class name (e.g., append a timestamp or UUID).

The group agent defaults to a plain `Agent` subclass; pass `modelly_agent_type`
to base it on a custom `Agent` subclass instead.

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

Models that search the same agents for alliances every step re-score every
candidate group on each `find_combinations` call. Wrap the scoring function
once with `cache_build` and pass the wrapper instead: each group is scored the
first time it is seen and served from the cache afterwards. Results and their
order are unchanged, provided the scoring function is deterministic for a
given group.

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

The cache is keyed by the exact tuple of agents passed to the scoring
function, so pass agents in a stable order (for example sorted by
`unique_id`) to get hits. It never expires by itself: call
`self.score.invalidate(agent)` when an agent's state changes or it leaves the
model (its groups are re-scored next time), or `self.score.invalidate()` to drop
everything. `maxsize` bounds the cache, evicting the oldest score first;
`score.hits` and `score.misses` show how well it works.

Removing an agent or group (`deactivate`, `dissolve`, or `agent.remove()`)
costs time proportional to that entity's own memberships, not to the total
number of memberships in the model.

### Reference

`MetaAgents` takes its lookups (`members_of`, `groups_of`, `query_memberships`, `at_level`) from
`modelly.behaviour.meta_agents.queries`; they are listed under `MetaAgents`.

```{eval-rst}
.. automodule:: modelly.behaviour.meta_agents.api
   :members:
   :inherited-members:
```

```{eval-rst}
.. automodule:: modelly.behaviour.meta_agents.views
   :members:
```

```{eval-rst}
.. automodule:: modelly.behaviour.meta_agents.meta_agent
   :members:
```

```{eval-rst}
.. automodule:: modelly.behaviour.meta_agents.combinations
   :members:
```
