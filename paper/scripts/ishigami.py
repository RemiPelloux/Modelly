"""Sobol indices of the Ishigami function, as the paper quotes them: data/ishigami.json.

    python paper/scripts/ishigami.py

Runs ``modelly.sensitivity.sobol`` with the test suite's settings (4,096 base samples,
seed 1, Jansen estimators) and writes the estimates with their bootstrap intervals next
to the analytical values. The paper's text is rounded from this file.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from environment import environment

from modelly.experiments import ScenarioSpace
from modelly.sensitivity import sobol

PAPER = Path(__file__).resolve().parents[1]
A, B = 7.0, 0.1
SAMPLES, SEED = 4096, 1
PI = math.pi
SPACE = ScenarioSpace(x1=(-PI, PI), x2=(-PI, PI), x3=(-PI, PI))


def ishigami(x1: float, x2: float, x3: float) -> float:
    """The Ishigami function with the usual a = 7 and b = 0.1."""
    return float(np.sin(x1) + A * np.sin(x2) ** 2 + B * x3**4 * np.sin(x1))


def analytical() -> dict[str, list[float]]:
    """The exact first-order and total indices."""
    v1 = 0.5 * (1 + B * PI**4 / 5) ** 2
    v2 = A**2 / 8
    v13 = B**2 * PI**8 * (1 / 18 - 1 / 50)
    v = v1 + v2 + v13
    return {"S1": [v1 / v, v2 / v, 0.0], "ST": [(v1 + v13) / v, v2 / v, v13 / v]}


def main() -> None:
    """Estimate, compare with the analytical values and write data/ishigami.json."""
    result = sobol(ishigami, SPACE, samples=SAMPLES, seed=SEED, estimator="jansen")
    table = result.table
    exact = analytical()
    out = {
        "environment": environment(),
        "samples": SAMPLES,
        "seed": SEED,
        "evaluations": result.info["evaluations"],
        "estimator": "jansen",
        "parameters": list(table.index),
        "analytical": exact,
        "estimate": {c: [float(v) for v in table[c]] for c in table.columns},
        "inside_intervals": bool(
            ((table["S1_low"] <= exact["S1"]) & (exact["S1"] <= table["S1_high"])).all()
            and (
                (table["ST_low"] <= exact["ST"]) & (exact["ST"] <= table["ST_high"])
            ).all()
        ),
    }
    (PAPER / "data" / "ishigami.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("estimate", "inside_intervals")}, indent=1))


if __name__ == "__main__":
    main()
