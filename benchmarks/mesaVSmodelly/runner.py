"""Execute a notebook headlessly, time every cell, and record outputs.

Usage:
    <venv-python> runner.py <notebook.ipynb> <framework> <results_dir>

Behaviour
---------
- chdir to the notebook's directory, so the CSVs it writes land next to it;
- delete any pre-existing ``*.csv`` there (guarantees a full, uncached run);
- force the Agg matplotlib backend (figures render, never open a window);
- inject ``display`` (the notebook calls it once);
- ``exec`` every code cell in one shared namespace, timing each;
- write ``<framework>.json`` into ``<results_dir>`` with per-cell + total
  timing, the hash of every CSV produced, and aggregate metrics.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path


def csv_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(df):  # pandas DataFrame
    numeric = df.select_dtypes(include="number")
    out = {"rows": len(df), "columns": list(df.columns)}
    if not numeric.empty:
        means = numeric.mean().round(4).to_dict()
        out["numeric_means"] = {k: float(v) for k, v in means.items()}
    return out


def main() -> None:
    notebook = Path(sys.argv[1]).resolve()
    framework = sys.argv[2]
    results_dir = Path(sys.argv[3]).resolve()

    os.chdir(notebook.parent)
    for stale in Path.cwd().glob("*.csv"):
        stale.unlink()

    os.environ["MPLBACKEND"] = "Agg"
    import matplotlib

    matplotlib.use("Agg", force=True)

    nb = json.loads(notebook.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]

    namespace: dict = {
        "__name__": "__runner__",
        "display": lambda *args, **kwargs: None,
    }

    per_cell: list[dict] = []
    total_started = time.perf_counter()
    for i, source in enumerate(cells):
        started = time.perf_counter()
        exec(compile(source, f"<cell {i}>", "exec"), namespace)  # noqa: S102
        elapsed = time.perf_counter() - started
        per_cell.append({"cell": i, "seconds": round(elapsed, 4)})
        print(
            f"[{framework}] cell {i:2d}/{len(cells) - 1}  {elapsed:7.2f}s", flush=True
        )
    total = time.perf_counter() - total_started

    # The framework version the notebook printed (mesa / modelly).
    for mod_name in ("modelly", "mesa"):
        if mod_name in namespace:
            version = getattr(namespace[mod_name], "__version__", "?")
            break
    else:
        version = "?"

    outputs: dict = {}
    for path in sorted(Path.cwd().glob("*.csv")):
        import pandas as pd

        df = pd.read_csv(path)
        outputs[path.name] = {"sha256": csv_sha256(path), **summarize(df)}

    result = {
        "framework": framework,
        "version": version,
        "total_seconds": round(total, 3),
        "per_cell": per_cell,
        "outputs": outputs,
    }
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{framework}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[{framework}] TOTAL {total:.2f}s", flush=True)


if __name__ == "__main__":
    main()
