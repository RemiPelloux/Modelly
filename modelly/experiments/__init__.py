"""Experiments and sweeps: parameter spaces and designs for a study."""

from modelly.experiments import designs
from modelly.experiments.designs import Design
from modelly.experiments.space import Choice, Fixed, Range, ScenarioSpace

__all__ = ["Choice", "Design", "Fixed", "Range", "ScenarioSpace", "designs"]
