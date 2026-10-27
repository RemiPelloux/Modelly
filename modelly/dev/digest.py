"""A stable SHA-256 digest of a run: its collected data and its final agent state.

The digest is taken over bytes of a canonical JSON form, the same on every operating
system and Python build: mapping keys sorted, no whitespace, ASCII only, floats
written exactly (``float.hex``) and agents written by ``unique_id``, never by
``repr`` (which would carry a memory address). With ``digits`` set, floats are
written rounded to that many significant digits instead, for outputs that pass
through platform maths libraries (see ``docs/determinism.md``).

Example:
    >>> from modelly.dev.digest import digest
    >>> digest({"x": [1, 0.5]}) == digest({"x": (1, 0.5)})
    True
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.timetravel.snapshot import model_state

if TYPE_CHECKING:
    from modelly.core.model import Model

ENCODING = "utf-8"
FLOAT_TAG = "f:"
BYTES_TAG = "b:"
PLAIN = (bool, int, str, type(None))


class DigestError(TypeError):
    """A value has no canonical form, so it cannot be part of a digest."""


def _float(value: float, digits: int | None) -> str:
    if digits is None or not np.isfinite(value):
        return FLOAT_TAG + float.hex(value)
    return FLOAT_TAG + f"{value:.{digits - 1}e}"


def _graph(value: Any, digits: int | None) -> dict[str, Any]:
    nodes = sorted((canonical(n, digits) for n in value.nodes), key=_key)
    edges = sorted(
        (
            sorted((canonical(n, digits) for n in edge), key=_key)
            for edge in value.edges
        ),
        key=_key,
    )
    return {"nodes": nodes, "edges": edges}


def _frame(value: Any, digits: int | None) -> dict[str, Any]:
    return {
        "columns": [str(column) for column in value.columns],
        "index": canonical(value.index.tolist(), digits),
        "data": [canonical(value[c].tolist(), digits) for c in value.columns],
    }


def _key(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _structured(value: Any, digits: int | None) -> Any:
    """Canonical form of containers and known library objects, or DigestError."""
    if isinstance(value, Mapping):
        return {str(k): canonical(v, digits) for k, v in value.items()}
    if isinstance(value, list | tuple | np.ndarray):
        return [canonical(item, digits) for item in value]
    if isinstance(value, set | frozenset):
        return sorted((canonical(item, digits) for item in value), key=_key)
    if hasattr(value, "unique_id") and hasattr(value, "model"):
        return {"agent": value.unique_id}
    if hasattr(value, "columns") and hasattr(value, "index"):
        return _frame(value, digits)
    if hasattr(value, "nodes") and hasattr(value, "edges"):
        return _graph(value, digits)
    raise DigestError(f"no canonical form for {type(value).__qualname__}")


def canonical(value: Any, digits: int | None = None) -> Any:
    """``value`` as plain JSON data with one spelling per value.

    Raises:
        DigestError: for an object with no canonical form (its ``repr`` is not stable).
    """
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, PLAIN):
        return value
    if isinstance(value, float):
        return _float(value, digits)
    if isinstance(value, bytes):
        return BYTES_TAG + value.hex()
    return _structured(value, digits)


def canonical_bytes(value: Any, digits: int | None = None) -> bytes:
    """The canonical JSON bytes of ``value``: sorted keys, no spaces, ASCII."""
    text = json.dumps(
        canonical(value, digits),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return text.encode(ENCODING)


def digest(value: Any, digits: int | None = None) -> str:
    """The SHA-256 hex digest of the canonical bytes of ``value``."""
    return hashlib.sha256(canonical_bytes(value, digits)).hexdigest()


def collected_data(model: Model[Any, Any]) -> dict[str, Any]:
    """The model's ``datacollector`` tables: model variables, and agent variables if any."""
    collector = getattr(model, "datacollector", None)
    if collector is None:
        return {}
    data = {"model": collector.get_model_vars_dataframe()}
    if collector.agent_reporters:
        data["agents"] = collector.get_agent_vars_dataframe()
    return data


def run_payload(model: Model[Any, Any]) -> dict[str, Any]:
    """What a run digest covers: collected data plus the final model and agent state."""
    return {"data": collected_data(model), "state": asdict(model_state(model))}


def run_digest(model: Model[Any, Any], digits: int | None = None) -> str:
    """The digest of ``run_payload(model)``."""
    return digest(run_payload(model), digits)
