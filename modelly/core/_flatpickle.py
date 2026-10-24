"""Pickle a model's agents flat, so the pickle's depth does not grow with the population.

A plain pickle of a model follows references depth first: an agent's neighbourhood holds a
cell, the cell holds its agents, each of those agents holds another neighbourhood, and so on
through the whole population. On a grid of a thousand agents that is over ten thousand nested
saves, past the recursion limit of Python 3.12 and 3.13 and the C stack of Windows.

So the agents go first, as empty shells (their class only), then their states, then the rest
of the model. The shells are in the pickler's memo by the time anything refers to them, so
every later reference to an agent is a memo lookup, not a nested save. One pickler writes the
three parts and one unpickler reads them, so they share the memo; the states are applied to
the shells before the rest of the model is read.
"""

from __future__ import annotations

import copyreg
import pickle
from typing import TYPE_CHECKING, Any, BinaryIO

if TYPE_CHECKING:
    from modelly.core.model import Model

FLAT_MARKER = "modelly-flat-agents"
# copyreg's reconstructors for objects whose state pickle applies after creating them.
_NEWOBJ = (copyreg.__newobj__, copyreg.__newobj_ex__)
_REDUCE_PARTS = 5  # (callable, args, state, list items, dict items)
_STATE_AND_SLOTS = 2  # a state of (instance dict, slot values)


def split(agent: Any, protocol: int) -> tuple[tuple, Any] | None:
    """``agent``'s (reconstructor, args) and its state, or None if it reduces another way."""
    reduced = agent.__reduce_ex__(protocol)
    if not isinstance(reduced, tuple) or len(reduced) != _REDUCE_PARTS:
        return None
    function, args, state, items, mapping = reduced
    if function not in _NEWOBJ or items is not None or mapping is not None:
        return None
    return (function, args), state


def apply_state(obj: Any, state: Any) -> None:
    """Set ``state`` on ``obj`` exactly as pickle's BUILD opcode would."""
    setstate = getattr(obj, "__setstate__", None)
    if setstate is not None:
        setstate(state)
        return
    slots = None
    if isinstance(state, tuple) and len(state) == _STATE_AND_SLOTS:
        state, slots = state
    if state:
        obj.__dict__.update(state)
    for name, value in (slots or {}).items():
        setattr(obj, name, value)


class ShellPickler(pickle.Pickler):
    """A pickler that writes the agents named in ``shells`` without their state."""

    def __init__(self, file: BinaryIO, protocol: int) -> None:
        """Pickle to ``file``; no shells until :func:`dump_flat` registers them."""
        super().__init__(file, protocol)
        self.protocol = protocol
        self.shells: dict[int, tuple] = {}

    def shell(self, obj: Any) -> Any:
        """The (reconstructor, args) of ``obj`` if it is a pending shell, else NotImplemented."""
        return self.shells.pop(id(obj), NotImplemented)


def dump_flat(pickler: ShellPickler, model: Model, payload: Any) -> None:
    """Write the shells, their states, then ``payload`` (which holds ``model``)."""
    agents, states = [], []
    for agent in list(model._all_agents):
        parts = split(agent, pickler.protocol)
        if parts is not None:
            pickler.shells[id(agent)] = parts[0]
            agents.append(agent)
            states.append(parts[1])
    pickler.dump((FLAT_MARKER, agents))
    pickler.shells.clear()
    pickler.dump(states)
    pickler.dump(payload)


def load_flat(file: BinaryIO) -> Any:
    """Read what :func:`dump_flat` wrote (or a plain one-part pickle) and return the payload."""
    unpickler = pickle.Unpickler(file)  # noqa: S301 - documented: trusted files only
    first = unpickler.load()
    if not (isinstance(first, tuple) and first and first[0] == FLAT_MARKER):
        return first
    agents = first[1]
    for agent, state in zip(agents, unpickler.load(), strict=True):
        apply_state(agent, state)
    return unpickler.load()
