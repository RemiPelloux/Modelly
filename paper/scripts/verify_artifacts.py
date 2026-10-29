"""Does every table and figure of the paper regenerate from the published data? A check.

    python paper/scripts/verify_artifacts.py            # regenerate into a scratch copy, compare
    python paper/scripts/verify_artifacts.py --quick    # skip the scripts that recompute data

Copies tables/ and figures/ aside, runs every generating script from the data files in
data/ and benchmarks/*/results/ (the ``analyse`` commands and the table scripts), and
compares the result with the committed files: tables byte for byte, figures pixel for
pixel (the PNG previews; the PDFs carry timestamps). The scripts that recompute a data
file from the code rather than from a result file (the Ishigami estimate, the scramblings,
the cohort counterexample, the graph cut, the assimilation numbers) are run too, and their
numbers compared with the committed data file, the environment record apart. Prints one
line per artifact and exits non-zero when any differs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
PYTHON = sys.executable
S = PAPER / "scripts"

# (what it regenerates, the command)
TABLE_COMMANDS = [
    ("playbooks, workloads, speedups figure", [PYTHON, S / "make_figures.py"]),
    ("speed-up intervals", [PYTHON, S / "bootstrap_ci.py"]),
    ("Mesa examples table", [PYTHON, S / "mesa_examples_table.py"]),
    ("sizes table", [PYTHON, S / "sizes.py", "analyse"]),
    ("recovery table", [PYTHON, S / "recovery.py", "analyse"]),
    *[
        (f"agreement {tag}", [PYTHON, S / "agreement.py", "analyse", "--tag", tag])
        for tag in (
            "small",
            "large",
            "small_baselines",
            "small_mesa3np",
            "large_grid_mesa3np",
            "large_grid200_new",
            "schelling300_new",
        )
    ],
    ("trajectory tables and figure", [PYTHON, S / "trajectories.py", "analyse"]),
    ("ABC sweep table", [PYTHON, S / "abc_sweep.py", "analyse"]),
    ("ablation table", [PYTHON, S / "ablation.py", "analyse"]),
    ("Python versions table", [PYTHON, S / "python_versions.py", "analyse"]),
    ("sweep table", [PYTHON, S / "sweep_e2e.py", "analyse"]),
    ("platform digests table", [PYTHON, S / "platform_digests_table.py"]),
]
# Scripts that recompute a data file from the code; compared on their numbers.
DATA_COMMANDS = [
    ("ishigami.json", [PYTHON, S / "ishigami.py"]),
    ("sobol_scramblings.json", [PYTHON, S / "sobol_scramblings.py"]),
    ("cohort_counterexample.json", [PYTHON, S / "cohort_counterexample.py"]),
    ("graph_cut.json", [PYTHON, S / "graph_cut.py"]),
    ("assimilation.json", [PYTHON, S / "assimilation.py"]),
]
VOLATILE = {"environment", "date", "commit"}


def strip(value):
    """The JSON value without its provenance record."""
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def run(command: list) -> str:
    """Run a generating command from the repository root; its stderr on failure."""
    completed = subprocess.run(
        [str(c) for c in command], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return "" if completed.returncode == 0 else completed.stderr[-800:]


def same_png(a: Path, b: Path) -> bool:
    """Pixel-for-pixel equality of two PNG files."""
    import matplotlib.image as mpimg  # noqa: PLC0415

    x, y = mpimg.imread(a), mpimg.imread(b)
    return x.shape == y.shape and bool((x == y).all())


def main() -> int:
    """Regenerate, compare, report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true", help="skip the data scripts")
    options = parser.parse_args()
    scratch = Path(tempfile.mkdtemp(prefix="modelly-paper-verify-"))
    committed = {}
    for folder in ("tables", "figures", "data"):
        shutil.copytree(PAPER / folder, scratch / folder)
        committed[folder] = scratch / folder
    failures = []
    for label, command in TABLE_COMMANDS:
        error = run(command)
        print(f"{'FAILED ' if error else 'ran    '} {label}")
        if error:
            failures.append(f"{label}: {error}")
    if not options.quick:
        for label, command in DATA_COMMANDS:
            error = run(command)
            print(f"{'FAILED ' if error else 'ran    '} {label}")
            if error:
                failures.append(f"{label}: {error}")
    # tables: byte for byte
    for path in sorted((PAPER / "tables").glob("*.tex")):
        before = committed["tables"] / path.name
        if not before.exists():
            print(f"NEW      tables/{path.name}")
            failures.append(f"tables/{path.name}: not committed")
        elif before.read_bytes() != path.read_bytes():
            print(f"DIFFERS  tables/{path.name}")
            failures.append(f"tables/{path.name}: differs from the committed file")
        else:
            print(f"same     tables/{path.name}")
    # figures: the PNG previews, pixel for pixel
    for path in sorted((PAPER / "figures").glob("*.png")):
        before = committed["figures"] / path.name
        if not before.exists() or not same_png(before, path):
            print(f"DIFFERS  figures/{path.name}")
            failures.append(f"figures/{path.name}: differs from the committed file")
        else:
            print(f"same     figures/{path.name}")
    # data recomputed by the scripts: the numbers, not the provenance
    if not options.quick:
        for name, _ in DATA_COMMANDS:
            before = json.loads((committed["data"] / name).read_text())
            after = json.loads((PAPER / "data" / name).read_text())
            if strip(before) != strip(after):
                print(f"DIFFERS  data/{name}")
                failures.append(f"data/{name}: the recomputed numbers differ")
            else:
                print(f"same     data/{name}")
            # keep the committed provenance record
            (PAPER / "data" / name).write_bytes((committed["data"] / name).read_bytes())
    shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print("\n" + "\n".join(failures))
        return 1
    print("\nevery table and figure regenerates from the published data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
