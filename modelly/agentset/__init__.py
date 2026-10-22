"""AgentSet related classes.

Core Objects: AgentSet, AbstractAgentSet, _HardKeyAgentSet, GroupBy.

Storage model
-------------
Both concrete sets are *ordered sets* backed by a ``dict`` whose values are
always ``None``; the dict gives O(1) membership and removal while preserving
insertion order (so shuffles and sorts are stable and reproducible).

* :class:`AgentSet` keys the dict on ``weakref.ref`` objects. A removed agent
  that nothing else references disappears from every ``AgentSet`` on its own.
  This is the type every *view* (select, shuffle, sort, groupby, ...) returns.
* :class:`_HardKeyAgentSet` keys the dict on the agents themselves. It is used
  only for the registries owned by :class:`~modelly.model.Model` whose lifecycle
  is explicit (``Agent.__init__`` / ``Agent.remove``).

Every bulk operation first takes a C-level snapshot (``list(dict)``) and then
walks the snapshot, so user code that adds or removes agents mid-iteration can
never corrupt the dict being walked.
"""

from modelly.agentset._utils import _resolve_per_agent_values, _resolve_weights
from modelly.agentset.abstract import AbstractAgentSet
from modelly.agentset.groupby import GroupBy
from modelly.agentset.strong import _HardKeyAgentSet
from modelly.agentset.weak import AgentSet

__all__ = [
    "AbstractAgentSet",
    "AgentSet",
    "GroupBy",
    "_HardKeyAgentSet",
    "_resolve_per_agent_values",
    "_resolve_weights",
]
