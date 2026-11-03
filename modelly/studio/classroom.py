"""Classroom mode: an instructor shares parameters, students submit runs, everyone sees them.

``modelly studio model.py:Model --classroom DIR`` points every student's Studio at one folder
(a shared drive, a synced folder, or one machine serving the whole class). In it:

* ``parameters.json``: the values the instructor shared (``share``), which every new session
  starts from;
* ``runs/``: one JSON file per submitted run (``submit``): who, the parameter values, the
  seed, the steps run and the final value of every model reporter.

The Classroom tab shows every submission as a table, so the class can compare its runs
(``submissions``). Files are written to a temporary name and renamed, so a half-written file is
never read.
"""

from __future__ import annotations

import datetime
import json
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from modelly.studio.session import StudioSession

PARAMETERS, RUNS = "parameters.json", "runs"
SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def _write(path: Path, data: Any) -> None:
    """Write JSON atomically: a temporary file, then a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    temporary.replace(path)


def shared_values(folder: str | Path) -> dict[str, Any]:
    """The parameters the instructor shared; empty when none were."""
    path = Path(folder) / PARAMETERS
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def share(session: StudioSession, folder: str | Path) -> Path:
    """Share the session's parameter values with the class."""
    path = Path(folder) / PARAMETERS
    _write(path, dict(session.values))
    return path


def _final(session: StudioSession) -> dict[str, float]:
    """The last value of every numeric model reporter."""
    collector = getattr(session.model, "datacollector", None)
    if collector is None:
        return {}
    frame = collector.get_model_vars_dataframe()
    numeric = frame.select_dtypes("number")
    return (
        {name: float(numeric[name].iloc[-1]) for name in numeric.columns}
        if len(numeric)
        else {}
    )


def submit(session: StudioSession, folder: str | Path, student: str) -> Path:
    """Save the live run for the class: who, the values, the seed, the steps, the results.

    Raises:
        ValueError: without a name.
    """
    name = SAFE.sub("-", student.strip()).strip("-")
    if not name:
        raise ValueError("give your name before submitting a run")
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    path = Path(folder) / RUNS / f"{stamp}-{name}-{uuid.uuid4().hex[:6]}.json"
    _write(path, {"student": student.strip(), "seed": session.seed,
                  "steps": float(session.model.time), "values": dict(session.values),
                  "results": _final(session)})  # fmt: skip
    return path


def submissions(folder: str | Path) -> pd.DataFrame:
    """Every submitted run, oldest first: student, seed, steps, values and results."""
    rows = []
    for path in sorted((Path(folder) / RUNS).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"student": data["student"], "seed": data["seed"], "steps": data["steps"],
                     **data["values"], **data["results"]})  # fmt: skip
    return pd.DataFrame(rows)
