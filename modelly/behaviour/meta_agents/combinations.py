"""Candidate meta-agent search: enumerate agent combinations and score them.

``evaluate_combination``, ``find_combinations`` and ``cache_build`` are exposed
as static methods of :class:`modelly.behaviour.meta_agents.MetaAgents`.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modelly.core.agent import Agent


def evaluate_combination(
    candidate_group: tuple[Agent, ...],
    evaluation_func: Callable[[tuple[Agent, ...]], float] | None,
) -> tuple[tuple[Agent, ...], float] | None:
    """Evaluate a candidate meta-agent group with a user-supplied function."""
    if evaluation_func is None:
        return None
    return candidate_group, evaluation_func(candidate_group)


def find_combinations(
    group: Iterable,
    size: int | tuple[int, int] = (2, 5),
    evaluation_func: Callable[[tuple[Agent, ...]], float] | None = None,
    filter_func: Callable[
        [list[tuple[tuple[Agent, ...], float]]],
        list[tuple[tuple[Agent, ...], float]],
    ]
    | None = None,
) -> list[tuple[tuple[Agent, ...], float]]:
    """Find candidate agent groups and score them with ``evaluation_func``.

    The helper discovers potential meta-agents before creating them. It
    deliberately does not mutate model or membership state.

    Args:
        group: The set of agents to find combinations in.
        size: The size or range of sizes for combinations. Defaults to (2, 5).
        evaluation_func: The function to evaluate combinations. Defaults to None.
        filter_func: Allows the user to specify how agents are filtered to form groups.
          Defaults to None.

    Returns:
        List: The list of valuable combinations, in a tuple first agentset of valuable combination  and then the value of
        the combination.
    """
    if isinstance(size, int):
        size_range = range(size, size + 1)
    else:
        min_size, max_size = size
        size_range = range(min_size, max_size + 1)

    combinations = []
    for candidate_group in itertools.chain.from_iterable(
        itertools.combinations(group, combination_size)
        for combination_size in size_range
    ):
        evaluation_result = evaluate_combination(candidate_group, evaluation_func)
        if evaluation_result is not None:
            _evaluated_group, result = evaluation_result
            if result is not None:
                combinations.append(evaluation_result)

    if combinations and filter_func is not None:
        return filter_func(combinations)
    return combinations


class CachedEvaluation:
    """Memoising wrapper around an ``evaluation_func``; built by ``cache_build``.

    Scores are stored per candidate group, keyed by the exact tuple
    ``find_combinations`` passes in, so a repeated search over the same agents
    only calls the wrapped function for groups it has not seen. The cache
    never expires on its own: call :meth:`invalidate` when the state a score
    depends on changes (for example when a member is removed or mutated).
    """

    def __init__(
        self,
        evaluation_func: Callable[[tuple[Agent, ...]], Any],
        maxsize: int | None = None,
    ) -> None:
        """Wrap ``evaluation_func``; keep at most ``maxsize`` scores (no limit if None)."""
        if not callable(evaluation_func):
            raise TypeError("evaluation_func must be callable")
        if maxsize is not None and maxsize < 1:
            raise ValueError(f"maxsize must be a positive integer, got {maxsize}")
        self.evaluation_func = evaluation_func
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self._scores: dict[tuple[Agent, ...], Any] = {}

    def __call__(self, candidate_group: tuple[Agent, ...]) -> Any:
        """Return the cached score of ``candidate_group``, computing it once."""
        key = tuple(candidate_group)
        if key in self._scores:
            self.hits += 1
            return self._scores[key]
        self.misses += 1
        score = self.evaluation_func(candidate_group)
        if self.maxsize is not None and len(self._scores) >= self.maxsize:
            # Evict the oldest entry: insertion order keeps eviction deterministic.
            del self._scores[next(iter(self._scores))]
        self._scores[key] = score
        return score

    def __len__(self) -> int:
        """Return the number of cached scores."""
        return len(self._scores)

    def invalidate(self, *agents: Agent) -> int:
        """Drop the scores of groups containing any of ``agents``; all if none given.

        Returns:
            The number of scores dropped.
        """
        if not agents:
            dropped = len(self._scores)
            self._scores.clear()
            return dropped
        targets = set(agents)
        stale = [key for key in self._scores if not targets.isdisjoint(key)]
        for key in stale:
            del self._scores[key]
        return len(stale)


def cache_build(
    evaluation_func: Callable[[tuple[Agent, ...]], Any],
    maxsize: int | None = None,
) -> CachedEvaluation:
    """Return a cached ``evaluation_func`` for repeated ``find_combinations`` calls.

    Models that search the same agents for meta-agents every step otherwise
    re-score every candidate group each time. Build the cache once and pass it
    as ``evaluation_func``; results and their order are unchanged as long as
    the wrapped function is deterministic for a given group.

    Args:
        evaluation_func: Scores one candidate group, as for ``find_combinations``.
        maxsize: Maximum number of cached scores; the oldest is evicted first.
            ``None`` (default) keeps every score.

    Returns:
        A callable :class:`CachedEvaluation` with ``hits``, ``misses`` and
        :meth:`~CachedEvaluation.invalidate`.

    Examples:
        >>> score = model.meta_agents.cache_build(shapley_value)
        >>> model.meta_agents.find_combinations(agents, size=2, evaluation_func=score)
        >>> score.invalidate(departed_agent)  # its groups are re-scored next time
    """
    return CachedEvaluation(evaluation_func, maxsize=maxsize)
