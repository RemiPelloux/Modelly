"""Attribute access (``get``, ``set``, ``agg``), shared by every agent set."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal, overload

from modelly._native.sets import attr_values
from modelly.core.agentset._utils import _resolve_per_agent_values

if TYPE_CHECKING:
    from modelly.core.agent import Agent
    from modelly.core.agentset.weak import AgentSet


class AttributeMixin[A: Agent]:
    """``get``, ``set`` and ``agg`` on top of the AbstractAgentSet primitives.

    Relies on the host providing ``to_list``.
    """

    def agg(
        self, attribute: str, func: Callable | Iterable[Callable]
    ) -> Any | list[Any]:
        """Aggregate an attribute of all agents in the AgentSet using one or more functions.

        Args:
            attribute (str): The name of the attribute to aggregate.
            func (Callable | Iterable[Callable]):
                - If Callable: A single function to apply to the attribute values (e.g., min, max, sum, np.mean)
                - If Iterable: Multiple functions to apply to the attribute values

        Returns:
            Any | [Any, ...]: Result of applying the function(s) to the attribute values.

        Examples:
            # Single function
            avg_energy = model.agents.agg("energy", np.mean)

            # Multiple functions
            min_wealth, max_wealth, total_wealth = model.agents.agg("wealth", [min, max, sum])
        """
        values = self.get(attribute)

        if isinstance(func, Callable):
            return func(values)
        else:
            return [f(values) for f in func]

    @overload
    def get(
        self,
        attr_names: str,
        handle_missing: Literal["error", "default"] = "error",
        default_value: Any = None,
    ) -> list[Any]: ...

    @overload
    def get(
        self,
        attr_names: list[str],
        handle_missing: Literal["error", "default"] = "error",
        default_value: Any = None,
    ) -> list[list[Any]]: ...

    def get(
        self,
        attr_names,
        handle_missing="error",
        default_value=None,
    ):
        """Retrieve the specified attribute(s) from each agent in the AgentSet.

        Args:
            attr_names (str | list[str]): The name(s) of the attribute(s) to retrieve from each agent.
            handle_missing (str, optional): How to handle missing attributes. Can be:
                                            - 'error' (default): raises an AttributeError if attribute is missing.
                                            - 'default': returns the specified default_value.
            default_value (Any, optional): The default value to return if 'handle_missing' is set to 'default'
                                           and the agent does not have the attribute.

        Returns:
            list[Any]: A list with the attribute value for each agent if attr_names is a str.
            list[list[Any]]: A list with a lists of attribute values for each agent if attr_names is a list of str.

        Raises:
            AttributeError: If 'handle_missing' is 'error' and the agent does not have the specified attribute(s).
            ValueError: If an unknown 'handle_missing' option is provided.
        """
        is_single_attr = isinstance(attr_names, str)
        agents = self.to_list()

        if handle_missing == "error":
            if is_single_attr:
                # operator.attrgetter's lookups, in one C loop when built
                return attr_values(agents, attr_names)
            return [[getattr(agent, attr) for attr in attr_names] for agent in agents]

        elif handle_missing == "default":
            if is_single_attr:
                return [getattr(agent, attr_names, default_value) for agent in agents]
            return [
                [getattr(agent, attr, default_value) for attr in attr_names]
                for agent in agents
            ]

        else:
            raise ValueError(
                f"Unknown handle_missing option: {handle_missing}, "
                "should be one of 'error' or 'default'"
            )

    def set(self, attr_name: str, value: Any) -> AgentSet[A]:
        """Set a specified attribute for the agents in the AgentSet.

        The behavior is derived from ``value`` (the same value-based rule pandas
        uses for column assignment):

        - A ``list``, ``tuple``, ``numpy.ndarray`` or ``pandas.Series`` is treated
          as one value per agent and is assigned element-wise, in iteration order
          (the same order ``get`` uses), so a ``get -> transform -> set``
          round-trip stays consistent. It must have the same length as the
          AgentSet; a length mismatch raises ``ValueError``.
        - Any other value (a scalar, a string, or any non-sequence) is broadcast:
          every agent receives the same value.

        Args:
            attr_name (str): The name of the attribute to set.
            value (Any): The value(s) to assign. See above for how the shape of
                ``value`` selects element-wise vs broadcast assignment.

        Returns:
            AgentSet: The AgentSet instance itself, after setting the attribute.

        Raises:
            ValueError: If ``value`` is a sequence whose length does not match the
                number of agents in the AgentSet.

        Notes:
            A per-agent sequence is recognized by its type (list, tuple, ndarray,
            Series). To assign a single sequence value to every agent, broadcast
            it explicitly, e.g. ``[shared_list] * len(agentset)``.
        """
        agents = self.to_list()
        for agent, agent_value in zip(
            agents, _resolve_per_agent_values(value, len(agents))
        ):
            setattr(agent, attr_name, agent_value)
        return self
