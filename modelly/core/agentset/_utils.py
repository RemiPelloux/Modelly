"""Helpers shared by the AgentSet implementations."""

from __future__ import annotations

import itertools
import math
import warnings
from collections.abc import Callable, Iterable, Sequence
from random import Random
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from modelly.core.agent import Agent


_MISSING = object()
_INF = float("inf")


def _resolve_weights(
    agents: Sequence[Agent],
    weights: str | Callable[[Agent], float] | Sequence[float],
) -> list[float]:
    """Extract and validate numerical weights for a sequence of agents.

    Args:
        agents: The sequence of agents to extract weights for.
        weights: Agent attribute name (str), weight callable, or sequence of floats.

    Returns:
        list[float]: Validated list of non-negative weights with positive sum.

    Raises:
        TypeError: If weights is of an unsupported type.
        ValueError: If sequence length does not match, if any weight is negative, or if total sum <= 0.
    """
    if isinstance(weights, str):
        w = [getattr(agent, weights) for agent in agents]
    elif callable(weights):
        w = [weights(agent) for agent in agents]
    elif isinstance(weights, Sequence):
        if len(weights) != len(agents):
            raise ValueError(
                f"Length of weights ({len(weights)}) does not match AgentSet length ({len(agents)})"
            )
        w = list(weights)
    else:
        raise TypeError(
            f"Unsupported weights type: {type(weights).__name__}. "
            "Expected str, Callable, Sequence[float], or None."
        )

    if not all(map(math.isfinite, w)):
        raise ValueError("All weights must be finite.")
    if any(x < 0 for x in w):
        raise ValueError("All weights must be non-negative.")
    if sum(w) <= 0:
        raise ValueError("Sum of weights must be strictly positive.")

    return w


def _resolve_per_agent_values(value: Any, n: int, *, strict: bool = True) -> Iterable:
    """Resolve ``value`` into an iterable of ``n`` per-agent values.

    A ``list``, ``tuple``, ``numpy.ndarray`` or ``pandas.Series`` of length ``n``
    is treated as one value per agent. Any other value (a scalar, a string, or a
    non-sequence) is broadcast to all ``n`` agents.

    Args:
        value: The value(s) to assign, either one per agent or broadcast.
        n: The number of agents to produce values for.
        strict: If True (the default), a sequence whose length is not ``n`` raises
            ValueError. If False, such a sequence is broadcast to every agent (the
            whole sequence becomes each agent's value).

    Returns:
        An iterable yielding exactly ``n`` values.

    Raises:
        ValueError: If ``strict`` and ``value`` is a sequence whose length is
            not ``n``.
    """
    if isinstance(value, (list, tuple, np.ndarray, pd.Series)):
        if len(value) == n:
            return value
        if strict:
            raise ValueError(
                f"sequence of length {len(value)} does not match the number "
                f"of agents ({n})"
            )
    return itertools.repeat(value, n)


def _resolve_random(random: Random | None, first_agent: Agent | None) -> Random:
    """Pick the rng for a new set: the one given, else the first agent's model rng.

    Falls back to a fresh, unseeded ``Random`` (with a warning) when the set is
    empty and no rng was given, since there is then nothing to derive one from.
    """
    if random is not None:
        return random
    if first_agent is not None:
        # all agents in an AgentSet should share the same model, just take it from first
        return first_agent.model.random
    warnings.warn(
        "No Agents specified in creation of AgentSet and no random number generator specified. "
        "This can make models non-reproducible. Please pass a random number generator explicitly",
        UserWarning,
        stacklevel=3,
    )
    return Random()


def _validate_at_most(at_most: int | float, size: int) -> int | float:
    """Validate ``at_most`` for select-like methods and resolve fractions to counts."""
    if isinstance(at_most, bool) or not isinstance(at_most, (int, float)):
        raise TypeError(
            f"at_most must be an integer or float, got {type(at_most).__name__}."
        )
    if isinstance(at_most, float) and at_most != _INF:
        if not (0.0 < at_most <= 1.0):
            raise ValueError(
                f"Fractional at_most must be in the range (0.0, 1.0], got {at_most}."
            )
        return int(size * at_most)  # Note that it rounds down (floor)
    if isinstance(at_most, int) and at_most < 0:
        raise ValueError(f"Integer at_most must be non-negative, got {at_most}.")
    return at_most
