"""A small JSON-schema subset, checked locally, and JSON read out of a model's reply.

Supported keywords: ``type`` (a name or a list of names), ``enum``, ``properties``,
``required``, ``additionalProperties: false``, ``items``, ``minimum``, ``maximum``,
``minLength``, ``maxLength``, ``minItems`` and ``maxItems``. Anything else in a schema
is refused, so a schema never looks enforced when it is not.

Example:
    >>> validate({"opinion": "agree"}, {"type": "object", "required": ["opinion"],
    ...     "properties": {"opinion": {"enum": ["agree", "disagree"]}}})
    {'opinion': 'agree'}
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from modelly.llm.errors import SchemaError

TYPES: dict[str, Callable[[Any], bool]] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}
# keyword -> (the type it applies to, how to measure, whether the bound holds, the problem)
BOUNDS = {
    "minimum": ("number", lambda v: v, lambda v, b: v >= b, "below the minimum"),
    "maximum": ("number", lambda v: v, lambda v, b: v <= b, "above the maximum"),
    "minLength": ("string", len, lambda v, b: v >= b, "shorter than minLength"),
    "maxLength": ("string", len, lambda v, b: v <= b, "longer than maxLength"),
    "minItems": ("array", len, lambda v, b: v >= b, "fewer items than minItems"),
    "maxItems": ("array", len, lambda v, b: v <= b, "more items than maxItems"),
}
STRUCTURE = frozenset(
    {"type", "enum", "properties", "required", "additionalProperties", "items"}
)
DOCUMENTATION = frozenset({"description", "title", "$schema"})
KNOWN = STRUCTURE | DOCUMENTATION | frozenset(BOUNDS)
FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
OPENERS = "{["


def validate(value: Any, schema: dict, path: str = "$") -> Any:
    """Return ``value`` when it matches ``schema``; raise :class:`SchemaError` otherwise.

    Args:
        value: Parsed JSON.
        schema: A schema using the supported keywords.
        path: Where ``value`` sits, for the error message.
    """
    unknown = set(schema) - KNOWN
    if unknown:
        raise ValueError(f"unsupported schema keywords at {path}: {sorted(unknown)}")
    check_type(value, schema, path)
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(path, f"{value!r} is not one of {schema['enum']!r}")
    check_bounds(value, schema, path)
    if isinstance(value, dict):
        check_object(value, schema, path)
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
    return value


def check_type(value: Any, schema: dict, path: str) -> None:
    """The ``type`` keyword: one name or a list of them."""
    if "type" not in schema:
        return
    names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    for name in names:
        if name not in TYPES:
            raise ValueError(f"unsupported type {name!r} at {path}")
    if not any(TYPES[name](value) for name in names):
        raise SchemaError(path, f"expected {' or '.join(names)}, got {value!r}")


def check_bounds(value: Any, schema: dict, path: str) -> None:
    """``minimum``, ``maximum`` and the length and item-count bounds."""
    for keyword, (kind, measure, holds, problem) in BOUNDS.items():
        applies = keyword in schema and TYPES[kind](value)
        if applies and not holds(measure(value), schema[keyword]):
            raise SchemaError(path, f"{value!r} is {problem} {schema[keyword]!r}")


def check_object(value: dict, schema: dict, path: str) -> None:
    """``required``, ``properties`` and ``additionalProperties: false``."""
    properties = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in value:
            raise SchemaError(path, f"missing required property {name!r}")
    for name, item in value.items():
        if name in properties:
            validate(item, properties[name], f"{path}.{name}")
        elif schema.get("additionalProperties", True) is False:
            raise SchemaError(path, f"unexpected property {name!r}")


def parse_json(text: str) -> Any:
    """The JSON value in a reply: plain, inside a code fence, or after some prose.

    Raises:
        SchemaError: When the reply holds no JSON value.
    """
    fenced = FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    candidate = candidate.strip()
    try:
        return json.loads(candidate)
    except ValueError:
        pass
    starts = [i for i, ch in enumerate(candidate) if ch in OPENERS]
    decoder = json.JSONDecoder()
    for start in starts:
        try:
            return decoder.raw_decode(candidate, start)[0]
        except ValueError:
            continue
    raise SchemaError("$", "the reply holds no JSON value")


def describe(schema: dict) -> str:
    """The schema as compact JSON, to put in a prompt."""
    return json.dumps(schema, sort_keys=True, separators=(",", ":"))
