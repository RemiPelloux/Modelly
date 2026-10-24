"""Candidate meta-agent search: enumerate agent combinations and score them.

Both functions are exposed as static methods of
:class:`modelly.behaviour.meta_agents.MetaAgents`.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

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
