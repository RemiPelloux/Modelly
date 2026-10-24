"""The catalogue of zoo models: one ``ZooModel`` per reference model.

Each model lives in ``modelly/zoo/<name>/model.py``, a single module that imports only
public ``modelly`` modules, so ``copy_model`` can write it into a new project unchanged.
The module docstring describes the model, its validation and its references.
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path


@dataclass(frozen=True)
class ZooModel:
    """One reference model of the zoo.

    Attributes:
        name: the zoo name (``modelly zoo info <name>``), also its package name.
        title: a human-readable title.
        field: the scientific field.
        model: the ``Model`` subclass, by name, in ``modelly.zoo.<name>.model``.
        scenario: its ``Scenario`` subclass, by name.
        summary: one sentence.
        validation: what the validation test checks.
    """

    name: str
    title: str
    field: str
    model: str
    scenario: str
    summary: str
    validation: str

    @property
    def module(self) -> str:
        """The dotted name of the model's module."""
        return f"modelly.zoo.{self.name}.model"

    @property
    def source(self) -> Path:
        """The path of the model's source file."""
        return Path(importlib.util.find_spec(self.module).origin)

    def load(self) -> tuple[type, type]:
        """Import the module and return ``(model class, scenario class)``."""
        module = importlib.import_module(self.module)
        return getattr(module, self.model), getattr(module, self.scenario)

    def doc(self) -> str:
        """The model module's docstring: the description and the references."""
        return importlib.import_module(self.module).__doc__ or ""


MODELS: tuple[ZooModel, ...] = (
    ZooModel(
        "age_seir",
        "Age-structured SEIR with contact matrices",
        "epidemiology",
        "AgeSEIR",
        "SEIRScenario",
        "SEIR over age groups mixing through a contact matrix, as binomial cohorts.",
        "attack rate against the final-size relation, within the CLT bound",
    ),
)


def names() -> list[str]:
    """The zoo names, in catalogue order."""
    return [entry.name for entry in MODELS]


def get(name: str) -> ZooModel:
    """The zoo model called ``name``.

    Raises:
        KeyError: if there is none; the message suggests the closest names.
    """
    for entry in MODELS:
        if entry.name == name:
            return entry
    close = get_close_matches(name, names())
    hint = f" Did you mean {', '.join(close)}?" if close else ""
    raise KeyError(f"No zoo model named {name!r}.{hint} See `modelly zoo list`.")
