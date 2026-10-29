"""The grid epidemic playbook's two engines as sweepable models (for sweep_e2e.py).

Importable by the process executor's workers: each class is the playbook's model with one
scalar reporter, ``infected``, the number infected after the last step.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "playbooks"))

_columns = importlib.import_module("grid_epidemic.modelly_model")
_mesa3 = importlib.import_module("grid_epidemic.mesa3_model")


class ColumnsSweep(_columns.Epidemic):
    """The column implementation with a scalar reporter."""

    @property
    def infected(self) -> int:
        """The number infected after the last step (0 before the first)."""
        return self.infected_history[-1] if self.infected_history else 0


class Mesa3Sweep(_mesa3.Epidemic):
    """The Mesa 3.5 implementation with a scalar reporter."""

    @property
    def infected(self) -> int:
        """The number infected after the last step (0 before the first)."""
        return self.infected_history[-1] if self.infected_history else 0
