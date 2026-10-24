"""GroupBy: the result of AgentSet.groupby."""

from __future__ import annotations

import operator
from collections.abc import Callable, Hashable
from typing import TYPE_CHECKING, Any

from modelly.core.agentset._utils import _MISSING

if TYPE_CHECKING:
    from modelly.core.agentset.abstract import AbstractAgentSet


class GroupBy:
    """Helper class for AgentSet.groupby.

    Attributes:
        groups (dict): A dictionary with the group_name as key and group as values

    """

    def __init__(self, groups: dict[Any, list | AbstractAgentSet]):
        """Initialize a GroupBy instance.

        Args:
            groups (dict): A dictionary with the group_name as key and group as values

        """
        self.groups: dict[Any, list | AbstractAgentSet] = dict(groups)

    def get_group(
        self, name: Hashable, default: Any = _MISSING
    ) -> list | AbstractAgentSet | Any:
        """Return the group for the given name.

        Args:
            name (Hashable): The group name to retrieve.
            default (Any, optional): Value to return when the group is missing.

        Raises:
            KeyError: If the group does not exist and no default is provided.
        """
        try:
            return self.groups[name]
        except KeyError as err:
            if default is not _MISSING:
                return default
            raise KeyError(f"No group found with name: {name}") from err

    def map(self, method: Callable | str, *args, **kwargs) -> dict[Any, Any]:
        """Apply the specified callable to each group and return the results.

        Args:
            method (Callable, str): The callable to apply to each group,

                                    * if ``method`` is a callable, it will be called it will be called with the group as first argument
                                    * if ``method`` is a str, it should refer to a method on the group

                                    Additional arguments and keyword arguments will be passed on to the callable.
            args: arguments to pass to the callable
            kwargs: keyword arguments to pass to the callable

        Returns:
            dict with group_name as key and the return of the method as value

        Notes:
            this method is useful for methods or functions that do return something. It
            will break method chaining. For that, use ``do`` instead.

        """
        if isinstance(method, str):
            return {
                k: getattr(v, method)(*args, **kwargs) for k, v in self.groups.items()
            }
        else:
            return {k: method(v, *args, **kwargs) for k, v in self.groups.items()}

    def do(self, method: Callable | str, *args, **kwargs) -> GroupBy:
        """Apply the specified callable to each group.

        Args:
            method (Callable, str): The callable to apply to each group,

                                    * if ``method`` is a callable, it will be called it will be called with the group as first argument
                                    * if ``method`` is a str, it should refer to a method on the group

                                    Additional arguments and keyword arguments will be passed on to the callable.
            args: arguments to pass to the callable
            kwargs: keyword arguments to pass to the callable

        Returns:
            the original GroupBy instance

        Notes:
            this method is useful for methods or functions that don't return anything and/or
            if you want to chain multiple do calls

        """
        if isinstance(method, str):
            for v in self.groups.values():
                getattr(v, method)(*args, **kwargs)
        else:
            for v in self.groups.values():
                method(v, *args, **kwargs)

        return self

    def count(self) -> dict[Any, int]:
        """Return the count of agents in each group.

        Returns:
            dict: A dictionary mapping group names to the number of agents in each group.
        """
        return {k: len(v) for k, v in self.groups.items()}

    def agg(self, attr_name: str, func: Callable) -> dict[Hashable, Any]:
        """Aggregate the values of a specific attribute across each group using the provided function.

        Args:
            attr_name (str): The name of the attribute to aggregate.
            func (Callable): The function to apply (e.g., sum, min, max, mean).

        Returns:
            dict[Hashable, Any]: A dictionary mapping group names to the result of applying the aggregation function.
        """
        getter = operator.attrgetter(attr_name)
        return {
            group_name: func(list(map(getter, group)))
            for group_name, group in self.groups.items()
        }

    def __iter__(self):  # noqa: D105
        return iter(self.groups.items())

    def __len__(self):  # noqa: D105
        return len(self.groups)

    def __repr__(self) -> str:
        """Return a representation showing each group's identifier and size."""
        sizes = {name: len(group) for name, group in self.groups.items()}
        return f"{type(self).__name__}({len(self)} groups: {sizes})"
