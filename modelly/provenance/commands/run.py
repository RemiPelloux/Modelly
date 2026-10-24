"""``modelly run``: run a model once and write its outputs and manifest."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from modelly.profile.loader import TargetError, parse_param
from modelly.provenance.commands.common import (
    EXIT_MODEL_ERROR,
    EXIT_OK,
    EXIT_USAGE,
    GUIDE,
    MODEL_OPTIONS,
    add_options,
    error,
    make_parser,
    positive,
)
from modelly.provenance.manifest import MANIFEST_NAME
from modelly.provenance.runner import RunSpec, run_study

PROG = "python -m modelly.provenance.commands.run"

DESCRIPTION = """\
Build a Modelly model, run it for --steps steps and write, in the --out folder:

  - one file per table its DataCollector holds: model.parquet (model reporters),
    agents.parquet (agent reporters), agents_<Class>.parquet (agent-type
    reporters), table_<name>.parquet (tables). Parquet needs pyarrow; without
    it, or for a table Parquet cannot hold, the file is CSV (UTF-8).
  - manifest.json: the code (git commit and a hash of the uncommitted diff when
    git is available, and a hash of every model source file), Modelly's version
    and build (compiled or pure Python), Python, the platform, the installed
    dependency versions, the scenario, the seeds, hashes of the --input files
    and of every output, and the wall and CPU time of the run.

Parameters the model's constructor takes by name go to it, the others to its
Scenario. Without --seed (or a 'seed' key in the scenario file) a seed is drawn
and recorded, so the run can still be repeated.
"""

EPILOG = f"""\
examples:
  modelly run model.py:Epidemic --scenario scenario.toml --steps 365 --out runs/
  modelly run model.py:Epidemic --steps 100 --seed 7 --param beta=0.3 --out runs/
  modelly run modelly.examples.basic.schelling.model:Schelling \\
      --steps 20 --seed 1 --out runs/schelling
  modelly run model.py:Epidemic --steps 100 --seed 1 --input data/contacts.csv \\
      --out runs/

scenario file (TOML, a flat table):
  seed = 42
  beta = 0.3
  width = 50

exit codes:
  0  the model ran; outputs and {MANIFEST_NAME} were written
  2  bad command line, or the target, scenario or an input cannot be used
  3  the model raised while being built or run (traceback on stderr)

guide: {GUIDE}
"""

OPTIONS = (
    *MODEL_OPTIONS,
    (("--steps",), {"type": positive, "required": True, "help": "steps to run"}),
    (
        ("--out",),
        {"type": Path, "required": True, "metavar": "DIR", "help": "folder to write"},
    ),
    (
        ("--input",),
        {
            "action": "append",
            "default": [],
            "type": Path,
            "metavar": "FILE",
            "help": "a data file the model reads; its hash is recorded; repeatable",
        },
    ),
)


def spec_from(argv: list[str] | None, prog: str) -> RunSpec:
    """Parse the command line into a RunSpec."""
    parser = make_parser(prog, DESCRIPTION, EPILOG)
    add_options(parser, OPTIONS)
    args = parser.parse_args(argv)
    return RunSpec(
        target=args.target,
        out=args.out,
        steps=args.steps,
        seed=args.seed,
        scenario=args.scenario,
        params=dict(parse_param(text) for text in args.param),
        inputs=tuple(args.input),
    )


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run the model and write its record; the exit status."""
    spec = spec_from(argv, prog)
    try:
        record = run_study(spec)
    except TargetError as problem:
        error(prog, problem)
        return EXIT_USAGE
    except Exception:  # any model error is reported, not raised
        traceback.print_exc()
        return EXIT_MODEL_ERROR
    tables = ", ".join(item["path"] for item in record["outputs"]) or "no tables"
    sys.stdout.write(
        f"{record['target']['class']}: {spec.steps} step(s), seed {record['run']['seed']}, "
        f"{record['timing']['wall_seconds']:.3f} s; wrote {tables} and "
        f"{(spec.out / MANIFEST_NAME).as_posix()}\n"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
