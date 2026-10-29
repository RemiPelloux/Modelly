"""The nowcasting tutorial's numbers, as the paper quotes them: data/assimilation.json.

    python paper/scripts/assimilation.py

Runs every Python block of docs/assimilation.md that needs no broker, as the test
``tests/stream/test_assimilation_tutorial.py`` does, and records the particle filter's
nowcast error against the free ensemble's, its resamplings, and the ensemble Kalman
filter's estimate of the contact rate with its spread, for the tutorial's one synthetic
dataset (truth seed 1, ensemble seeds 2 and 3). The paper's text is rounded from this file.
"""

from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

from environment import environment

PAPER = Path(__file__).resolve().parents[1]
TUTORIAL = PAPER.parent / "docs" / "assimilation.md"
BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
NOT_RUN = "# Not run here"
MODULE = "assimilation_tutorial"


def run_tutorial() -> types.ModuleType:
    """The tutorial's namespace after running it as an importable module."""
    blocks = BLOCK.findall(TUTORIAL.read_text(encoding="utf-8"))
    code = "\n".join(b for b in blocks if not b.startswith(NOT_RUN))
    module = types.ModuleType(MODULE)
    sys.modules[MODULE] = module
    exec(compile(code, str(TUTORIAL), "exec"), module.__dict__)  # noqa: S102 - own tutorial
    return module


def record(t: types.ModuleType) -> dict[str, object]:
    """The quantities the paper reports, with the settings they came from."""
    enkf_last = t.enkf.history.iloc[-1].to_dict()
    return {
        "environment": environment(),
        "seeds": {"truth": 1, "filtered_and_free_ensembles": 2, "kalman_ensemble": 3},
        "datasets": 1,
        "days": int(t.DAYS),
        "replicates": int(t.REPLICATES),
        "true_beta": float(getattr(t, "TRUE_BETA", getattr(t, "BETA", 0.45))),
        "rmse_filtered": float(t.rmse_filtered),
        "rmse_free": float(t.rmse_free),
        "ratio": float(t.rmse_filtered / t.rmse_free),
        "resamplings": int(t.pf.resamplings),
        "particle_filter_beta": float(t.pf_beta),
        "enkf_beta_estimate": float(t.beta_estimate),
        "enkf_history_last": {k: float(v) for k, v in enkf_last.items()},
    }


def main() -> None:
    """Run the tutorial and write data/assimilation.json."""
    out = record(run_tutorial())
    (PAPER / "data" / "assimilation.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
