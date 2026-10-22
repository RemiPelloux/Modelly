"""Filtering and sampling, shared by every agent set."""

from __future__ import annotations

import copy
import numbers
import operator
from collections.abc import Callable, Sequence
from random import Random
from typing import TYPE_CHECKING

import numpy as np

from modelly.agentset._utils import _INF, _resolve_weights, _validate_at_most

if TYPE_CHECKING:
    from modelly.agent import Agent
    from modelly.agentset.abstract import AbstractAgentSet


class SelectionMixin[A: Agent]:
    """``select`` and ``select_random`` on top of the AbstractAgentSet primitives.

    Relies on the host providing ``__len__``, ``to_list``, ``_update``, ``_view``
    and ``random``.
    """

    random: Random

    def select(
        self,
        filter_func: Callable[[A], bool] | None = None,
        at_most: int | float = _INF,
        inplace: bool = False,
        agent_type: type[A] | None = None,
    ) -> AbstractAgentSet[A]:
        """Select a subset of agents from the AbstractAgentSet based on a filter function and/or quantity limit.

        Args:
            filter_func (Callable[[Agent], bool], optional): A function that takes an Agent and returns True if the
                agent should be included in the result. Defaults to None, meaning no filtering is applied.
            at_most (int | float, optional): The maximum amount of agents to select. Defaults to infinity.
              - If an integer, at most the first number of matching agents are selected.
              - If a float between 0 and 1, at most that fraction of original the agents are selected.
            inplace (bool, optional): If True, modifies the current AbstractAgentSet; otherwise, returns a new AbstractAgentSet. Defaults to False.
            agent_type (type[Agent], optional): The class type of the agents to select. Defaults to None, meaning no type filtering is applied.

        Returns:
            AbstractAgentSet: A new AbstractAgentSet containing the selected agents, unless inplace is True, in which case the current AbstractAgentSet is updated.

        Raises:
            TypeError: If at_most is not an integer or float, or is a boolean.
            ValueError: If at_most is a negative integer, or a float not in the range (0.0, 1.0].

        Notes:
            - at_most just return the first n or fraction of agents. To take a random sample, shuffle() beforehand.
            - at_most is an upper limit. When specifying other criteria, the number of agents returned can be smaller.
        """
        if filter_func is None and agent_type is None and at_most == _INF:
            return self if inplace else copy.copy(self)

        at_most = _validate_at_most(at_most, len(self))

        # One pass, comprehension-based: a generator with a running count is
        # 2-3x slower for the common unbounded case.
        agents = self.to_list()
        if agent_type is not None:
            agents = [a for a in agents if isinstance(a, agent_type)]
        if filter_func is not None:
            agents = [a for a in agents if filter_func(a)]
        if at_most != _INF:
            agents = agents[:at_most]

        return self._update(agents) if inplace else self._view(agents)

    def select_random(
        self,
        n: int | float = 1,
        *,
        weights: str | Callable[[A], float] | Sequence[float] | None = None,
        replace: bool = False,
        inplace: bool = False,
    ) -> AbstractAgentSet[A]:
        """Select a random or weighted sample of agents from the AbstractAgentSet.

        Args:
            n (int | float, optional): The number or fraction of agents to select. Defaults to 1.
                - If an integer >= 1, the number of agents to select.
                - If a float in (0, 1], the fraction of agents to select.
            weights (str | Callable[[Agent], float] | Sequence[float] | None, optional): Weights for selection.
                - If a str: uses the specified agent attribute name.
                - If a Callable: calls the function on each agent to compute its weight.
                - If a Sequence: a sequence of numerical weights of the same length as the AgentSet.
                - If None: uniform random selection. Defaults to None.
            replace (bool, optional): Whether to sample with replacement. Defaults to False.
            inplace (bool, optional): If True, modifies the current AbstractAgentSet; otherwise, returns a new AbstractAgentSet. Defaults to False.

        Returns:
            AbstractAgentSet: A new or updated AbstractAgentSet containing the sampled agents.

        Raises:
            ValueError: If the AgentSet is empty, n <= 0, n > len(self) when replace=False, n exceeds the number of positive weights when sampling without replacement, weights are negative, total weight <= 0, or length of weights sequence does not match the AgentSet.
            TypeError: If n or weights is of an unsupported type.
        """
        if len(self) == 0:
            raise ValueError("Cannot sample from an empty AgentSet.")

        # numbers.Integral / numbers.Real also cover numpy scalars such as np.int64
        if isinstance(n, (bool, np.bool_)) or not isinstance(n, numbers.Real):
            raise TypeError(f"n must be an integer or float, got {type(n).__name__}.")

        if isinstance(n, numbers.Integral):
            n = int(n)
            if n <= 0:
                raise ValueError(f"n must be a positive integer, got {n}.")
            sample_size = n
        else:  # float
            if not (0.0 < n <= 1.0):
                raise ValueError(
                    f"Fractional sample size n must be in the range (0.0, 1.0], got {n}."
                )
            sample_size = int(len(self) * n)

        if not replace and sample_size > len(self):
            raise ValueError(
                f"Sample size ({sample_size}) cannot exceed AgentSet size ({len(self)}) when replace=False."
            )

        if sample_size == 0:
            return self._update([]) if inplace else self._view([])

        items = self.to_list()

        if weights is None:
            if replace:
                chosen = self.random.choices(items, k=sample_size)
            else:
                chosen = self.random.sample(items, k=sample_size)
        else:
            w = _resolve_weights(items, weights)

            if replace:
                chosen = self.random.choices(items, weights=w, k=sample_size)
            else:
                # Efraimidis & Spirakis (A-Res) algorithm for weighted sampling without replacement
                random = self.random.random
                keys = [
                    (random() ** (1.0 / wi), agent)
                    for agent, wi in zip(items, w)
                    if wi > 0
                ]

                positive_weight_count = len(keys)
                if sample_size > positive_weight_count:
                    raise ValueError(
                        f"Sample size ({sample_size}) cannot exceed the number of "
                        f"agents with positive weights ({positive_weight_count}) when "
                        "replace=False."
                    )
                keys.sort(key=operator.itemgetter(0), reverse=True)
                chosen = [agent for _, agent in keys[:sample_size]]

        return self._update(chosen) if inplace else self._view(chosen)
