"""The Python half of the browser runner: what the page's Web Worker calls in Pyodide.

``BrowserRun`` builds the model from the parameter panel's values, advances it a few
steps at a time and reports what the page draws. Values cross the JavaScript boundary as
JSON strings, so the worker never holds a Python object but the run itself.

The panel's fields are Studio's (``modelly.studio.params``), encoded for the page by
``encode_parameter``: a ``choice`` sends the index of the selected value, a ``fixed``
field is shown as its ``repr`` and keeps its default.
"""

from __future__ import annotations

import importlib.util
import json
import time
from typing import Any

from modelly.profile.loader import build_model
from modelly.studio.loader import load_model_class
from modelly.studio.params import BOOL, CHOICE, FIXED, FLOAT, FRACTION, INT, Parameter
from modelly.studio.params import parameters_of as studio_parameters
from modelly.web.snapshot import CLASS, colour_attributes, series_rows, space_view

NATIVE_MODULES = ("fastrng", "fastloop", "fastcell", "fastset")
# A run hands control back to the page about this often, so Stop is heard.
STEP_BUDGET_S = 0.05
CASTS = {BOOL: bool, INT: int, FLOAT: float, FRACTION: float}


def _label(choice: Any) -> str:
    """How a select shows ``choice``: an Enum member's name, else its text."""
    return str(getattr(choice, "name", choice))


def encode_parameter(parameter: Parameter) -> dict[str, Any]:
    """``parameter`` as the JSON the page builds its field from."""
    default = parameter.default
    if parameter.kind == CHOICE:
        default = list(parameter.choices).index(default)
    elif parameter.kind == FIXED:
        default = repr(default)
    return {
        "name": parameter.name,
        "kind": parameter.kind,
        "default": default,
        "choices": [_label(choice) for choice in parameter.choices],
    }


def decode_value(parameter: Parameter, raw: Any) -> Any:
    """The value the page sent for ``parameter``, as the model takes it."""
    if parameter.kind == CHOICE:
        return parameter.choices[int(raw)]
    cast = CASTS.get(parameter.kind, str)
    return cast(raw)


def describe(model_class: type) -> list[dict[str, Any]]:
    """The parameter panel of ``model_class``, encoded for the page."""
    return [encode_parameter(p) for p in studio_parameters(model_class)]


def native_modules() -> list[str]:
    """The compiled ``modelly._native`` modules this interpreter can import."""
    return [
        name
        for name in NATIVE_MODULES
        if importlib.util.find_spec(f"modelly._native.{name}") is not None
    ]


class BrowserRun:
    """One model in a browser tab, rebuilt by ``build`` and advanced by ``advance``."""

    def __init__(self, target: str) -> None:
        """Load the model class ``target`` names (``package.module:Class``)."""
        self.model_class = load_model_class(target)
        self.parameters = {p.name: p for p in studio_parameters(self.model_class)}
        self.model = None
        self.steps = 0
        self._rows = 0

    def build(self, values_json: str, seed: int) -> None:
        """A new model from the panel's ``values`` (JSON, by name) and ``seed``."""
        values = {
            name: decode_value(self.parameters[name], raw)
            for name, raw in json.loads(values_json).items()
            if name in self.parameters and self.parameters[name].kind != FIXED
        }
        self.model = build_model(self.model_class, values, seed)
        self.steps, self._rows = 0, 0

    def advance(self, steps: int, budget_s: float = STEP_BUDGET_S) -> int:
        """Up to ``steps`` steps, fewer when the time budget ends or the model stops."""
        deadline = time.perf_counter() + budget_s
        done = 0
        while done < steps and self.model.running:
            self.model.step()
            done += 1
            if time.perf_counter() >= deadline:
                break
        self.steps += done
        return done

    def state_json(self, colour_by: str = CLASS) -> str:
        """The page's view of the run: time, the new reporter rows and the space."""
        series = series_rows(self.model, self._rows)
        if series:
            self._rows += len(next(iter(series.values())))
        return json.dumps(
            {
                "steps": self.steps,
                "time": float(self.model.time),
                "running": bool(self.model.running),
                "series": series,
                "space": space_view(self.model, colour_by),
                "attributes": colour_attributes(self.model),
            }
        )


__all__ = [
    "BrowserRun",
    "decode_value",
    "describe",
    "encode_parameter",
    "native_modules",
]
