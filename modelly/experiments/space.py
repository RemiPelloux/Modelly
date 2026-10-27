"""The parameter space of an experiment: ranges, choices and fixed values.

A :class:`ScenarioSpace` names every scenario parameter an experiment sets.
A ``(low, high)`` tuple is a :class:`Range`, a list is a :class:`Choice`,
anything else is :class:`Fixed`::

    space = ScenarioSpace(beta=(0.05, 0.5), n=(50, 200), policy=["none", "lockdown"], width=20)

Designs (:mod:`modelly.experiments.designs`) sample the varying dimensions in
the unit cube; :meth:`ScenarioSpace.point` maps one sample to parameter values.
:meth:`ScenarioSpace.typed` checks the names and types against a Scenario class.
"""

from __future__ import annotations

import math
import typing
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

RANGE_LENGTH = 2  # a (low, high) tuple


def _plain(value: Any) -> Any:
    """A numpy scalar as the Python value it holds; anything else unchanged."""
    return value.item() if isinstance(value, np.generic) else value


def _is_int(value: Any) -> bool:
    """Whether ``value`` is an integer, booleans excluded."""
    return isinstance(value, int | np.integer) and not isinstance(value, bool)


@dataclass(frozen=True)
class Range:
    """A continuous (or integer) interval ``[low, high]``, optionally on a log scale.

    Example:
        >>> Range(0.05, 0.5).from_unit(0.5)
        0.275
    """

    low: float
    high: float
    log: bool = False
    integer: bool = False

    def __post_init__(self) -> None:
        """Reject an empty interval and a log scale that reaches zero."""
        if not self.low < self.high:
            raise ValueError(f"Range needs low < high, got ({self.low}, {self.high})")
        if self.log and self.low <= 0:
            raise ValueError("a log-scale Range needs low > 0")

    def from_unit(self, u: float) -> float | int:
        """The value at position ``u`` in ``[0, 1)`` of the interval."""
        if self.integer:
            width = int(self.high) - int(self.low) + 1
            return int(self.low) + min(int(u * width), width - 1)
        if self.log:
            low, high = math.log(self.low), math.log(self.high)
            return float(math.exp(low + u * (high - low)))
        return float(self.low + u * (self.high - self.low))

    def levels(self, count: int) -> list[float | int]:
        """``count`` evenly spaced values from low to high (fewer for a short integer range)."""
        if count < 1:
            raise ValueError(f"levels must be at least 1, got {count}")
        bounds = (math.log(self.low), math.log(self.high)) if self.log else None
        grid = np.linspace(*(bounds or (self.low, self.high)), count)
        values = np.exp(grid) if self.log else grid
        if self.integer:
            return list(dict.fromkeys(round(float(v)) for v in values))
        return [float(v) for v in values]


@dataclass(frozen=True)
class Choice:
    """One of a list of values, each equally likely under a random design.

    Example:
        >>> Choice(["a", "b"]).from_unit(0.75)
        'b'
    """

    values: tuple[Any, ...]

    def __init__(self, values: Sequence[Any]) -> None:
        """Keep the values as a tuple of plain Python values."""
        if not values:
            raise ValueError("Choice needs at least one value")
        object.__setattr__(self, "values", tuple(_plain(v) for v in values))

    def from_unit(self, u: float) -> Any:
        """The value whose share of ``[0, 1)`` contains ``u``."""
        count = len(self.values)
        return self.values[min(int(u * count), count - 1)]

    def levels(self, count: int | None = None) -> list[Any]:
        """Every value (a factorial design takes them all)."""
        return list(self.values)


@dataclass(frozen=True)
class Fixed:
    """A value every run takes."""

    value: Any


Dimension = Range | Choice


def as_dimension(value: Any) -> Range | Choice | Fixed:
    """A Range for a ``(low, high)`` tuple, a Choice for a list, else Fixed."""
    if isinstance(value, Range | Choice | Fixed):
        return value
    if isinstance(value, tuple):
        if len(value) != RANGE_LENGTH:
            raise TypeError(f"a range is a (low, high) tuple, got {value!r}")
        integer = all(_is_int(v) for v in value)
        return Range(_plain(value[0]), _plain(value[1]), integer=integer)
    if isinstance(value, list):
        return Choice(value)
    return Fixed(_plain(value))


@dataclass(frozen=True)
class ScenarioSpace:
    """Every scenario parameter an experiment sets, varying or fixed.

    Example:
        >>> space = ScenarioSpace(beta=(0.1, 0.3), policy=["a", "b"], n=100)
        >>> space.point([0.5, 0.0])
        {'beta': 0.2, 'policy': 'a', 'n': 100}
    """

    parameters: dict[str, Range | Choice | Fixed] = field(default_factory=dict)

    def __init__(self, parameters: Mapping[str, Any] | None = None, /, **named: Any):
        """Build the space from a mapping and/or keyword arguments."""
        merged = {**(parameters or {}), **named}
        dims = {name: as_dimension(value) for name, value in merged.items()}
        object.__setattr__(self, "parameters", dims)

    @property
    def names(self) -> list[str]:
        """Every parameter name, in declaration order."""
        return list(self.parameters)

    @property
    def dimensions(self) -> dict[str, Dimension]:
        """The varying parameters (ranges and choices), in declaration order."""
        return {
            name: dim
            for name, dim in self.parameters.items()
            if not isinstance(dim, Fixed)
        }

    @property
    def fixed(self) -> dict[str, Any]:
        """The fixed parameters and their values."""
        return {
            name: dim.value
            for name, dim in self.parameters.items()
            if isinstance(dim, Fixed)
        }

    def point(self, unit: Sequence[float] | np.ndarray) -> dict[str, Any]:
        """The parameters at ``unit``, one coordinate in ``[0, 1)`` per dimension."""
        dims = self.dimensions
        if len(unit) != len(dims):
            raise ValueError(f"expected {len(dims)} coordinates, got {len(unit)}")
        values = {
            name: dim.from_unit(float(u)) for (name, dim), u in zip(dims.items(), unit)
        }
        return {name: values.get(name, self.fixed.get(name)) for name in self.names}

    def complete(self, values: Mapping[str, Any]) -> dict[str, Any]:
        """``values`` with the fixed parameters added; unknown names are an error."""
        unknown = set(values) - set(self.names)
        if unknown:
            raise ValueError(f"parameters not in the space: {sorted(unknown)}")
        merged = {**self.fixed, **{k: _plain(v) for k, v in values.items()}}
        return {name: merged[name] for name in self.names if name in merged}

    def typed(self, scenario: type) -> ScenarioSpace:
        """This space checked against ``scenario``'s declared fields and their types.

        Unknown names are a ValueError; a range or value of the wrong type is a
        TypeError. A Range with whole-number bounds over an ``int`` field becomes an
        integer Range.
        """
        hints = typing.get_type_hints(scenario)
        declared = set(getattr(scenario, "_scenario_defaults", {})) | {
            name for name in hints if not name.startswith("_")
        }
        unknown = [name for name in self.names if name not in declared]
        if unknown:
            raise ValueError(
                f"{scenario.__name__} declares no parameter(s) {unknown}; "
                f"it declares {sorted(declared)}"
            )
        return ScenarioSpace(
            {
                name: _typed(name, dim, hints.get(name))
                for name, dim in self.parameters.items()
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready description of the space (for the store's fingerprint)."""
        return {
            name: {"kind": type(dim).__name__, **vars(dim)}
            for name, dim in self.parameters.items()
        }


def _typed(name: str, dim: Range | Choice | Fixed, hint: Any) -> Range | Choice | Fixed:
    """``dim`` checked against the field's annotation ``hint`` (plain classes only)."""
    if hint not in (int, float, bool, str):
        return dim
    if isinstance(dim, Range):
        return _typed_range(name, dim, hint)
    values = dim.values if isinstance(dim, Choice) else (dim.value,)
    for value in values:
        if not _matches(value, hint):
            raise TypeError(f"{name} is {hint.__name__}, got {value!r}")
    return dim


def _typed_range(name: str, dim: Range, hint: type) -> Range:
    """A Range over a float field is continuous, over an int field whole; bool and str take none."""
    if hint is float:
        return Range(float(dim.low), float(dim.high), log=dim.log)
    whole = float(dim.low).is_integer() and float(dim.high).is_integer()
    if hint is int and whole:
        return Range(int(dim.low), int(dim.high), log=dim.log, integer=True)
    raise TypeError(
        f"{name} is {hint.__name__}: a Range({dim.low}, {dim.high}) cannot set it"
    )


def _matches(value: Any, hint: type) -> bool:
    """Whether ``value`` fits a field annotated ``hint`` (an int fits a float)."""
    if hint is float:
        return isinstance(value, float | int) and not isinstance(value, bool)
    if hint is int:
        return _is_int(value)
    return isinstance(value, hint)
