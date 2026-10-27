"""Command line for ``python -m modelly.experiments`` (``modelly experiment``)."""

from __future__ import annotations

import argparse
import sys
import tomllib
from typing import Any

from modelly.experiments.executors import available_executors
from modelly.experiments.experiment import Experiment, ExperimentError, RunReport
from modelly.experiments.spec import RunSettings, SpecError, load_spec
from modelly.experiments.store import StoreMismatchError
from modelly.profile.loader import TargetError

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
GUIDE = "https://remipelloux.github.io/Modelly/experiments.html"
PROG = "python -m modelly.experiments"

DESCRIPTION = """\
Run a parameter study described in a TOML file: a model, a parameter space, a
design (full factorial, Latin hypercube, Sobol, Halton or a list of points),
replicates, steps and outputs. Every run writes one Parquet file to the store
folder; a rerun skips the runs already there, so an interrupted sweep resumes
where it stopped and gives the same numbers on any executor."""

EPILOG = f"""\
commands:
  run SPEC      run every pending run of the experiment
  status SPEC   count finished, failed and pending runs

examples:
  modelly experiment run study.toml
  modelly experiment run study.toml --executor threads --max-parallel 4
  modelly experiment run study.toml --executor slurm   # [run.options] has the queue
  modelly experiment run study.toml --dry-run          # what would run, nothing runs
  modelly experiment status study.toml

a minimal spec:
  [experiment]
  model = "model.py:Epidemic"
  steps = 100
  replicates = 10
  outputs = ["infected"]
  store = "runs/epidemic"
  [space]
  beta = {{ min = 0.05, max = 0.5 }}
  vaccination = [0.0, 0.2]
  [design]
  kind = "latin_hypercube"
  n = 64

executors: {", ".join(available_executors())}

exit codes:
  {EXIT_OK}  every run finished (or, for status, nothing failed)
  {EXIT_FAILED}  at least one run failed (details in the store's failures/ folder)
  {EXIT_USAGE}  bad command line, unreadable spec, or a store of another experiment

guide: {GUIDE}"""


def build_parser(prog: str = PROG) -> argparse.ArgumentParser:
    """The parser with the ``run`` and ``status`` subcommands."""
    layout: dict[str, Any] = {
        "epilog": EPILOG,
        "formatter_class": argparse.RawDescriptionHelpFormatter,
    }
    parser = argparse.ArgumentParser(prog=prog, description=DESCRIPTION, **layout)
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    run = commands.add_parser(
        "run", help="run the pending runs", description=DESCRIPTION, **layout
    )
    run.add_argument("spec", help="the experiment's TOML file")
    run.add_argument("--executor", help="override [run] executor")
    run.add_argument("--max-parallel", type=int, help="override [run] max_parallel")
    run.add_argument("--dry-run", action="store_true", help="list what would run")
    run.add_argument("--progress", action="store_true", help="show a progress bar")
    status = commands.add_parser(
        "status", help="count runs", description="Count the runs.", **layout
    )
    status.add_argument("spec", help="the experiment's TOML file")
    return parser


def _status(experiment: Experiment) -> int:
    """Write the run counts; exit 1 when a recorded failure is pending."""
    tasks = experiment.tasks()
    finished, failed = experiment.store.finished(), experiment.store.failed()
    done = sum(task.seed in finished for task in tasks)
    broken = sum(task.seed in failed and task.seed not in finished for task in tasks)
    sys.stdout.write(
        f"{len(experiment.points)} points x {experiment.replicates} replicates: "
        f"{done} finished, {broken} failed, {len(tasks) - done} pending\n"
    )
    return EXIT_FAILED if broken else EXIT_OK


def _run(
    experiment: Experiment, settings: RunSettings, args: argparse.Namespace
) -> int:
    """Run (or list, with --dry-run) the pending runs; the exit status."""
    executor = args.executor or settings.executor
    limit = args.max_parallel or settings.max_parallel
    if args.dry_run:
        pending = experiment.pending()
        sys.stdout.write(f"{len(pending)} runs pending on {executor}\n")
        for task in pending:
            sys.stdout.write(f"  {task.run_id}  seed {task.seed}  {task.params}\n")
        return EXIT_OK
    report = experiment.run(executor, limit, progress=args.progress, **settings.options)
    sys.stdout.write(_summary(report, experiment))
    return EXIT_OK if report.ok else EXIT_FAILED


def _summary(report: RunReport, experiment: Experiment) -> str:
    """One line per outcome count, and where the results are."""
    counts = f"{report.done} runs finished, {len(report.failed)} failed, "
    counts += f"{report.skipped} already in the store (of {report.total})"
    lines = [counts, f"results: {experiment.store.path}"]
    lines += [
        f"failed: {outcome.run_id} (seed {outcome.seed})" for outcome in report.failed
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run the command line; the exit status."""
    args = build_parser(prog).parse_args(argv)
    try:
        experiment, settings = load_spec(args.spec)
        if args.command == "status":
            return _status(experiment)
        return _run(experiment, settings, args)
    except ExperimentError as error:
        sys.stderr.write(f"{prog}: {error}\n")
        return EXIT_FAILED
    except (
        OSError,
        tomllib.TOMLDecodeError,
        SpecError,
        StoreMismatchError,
        TargetError,
        TypeError,
        ValueError,
        ImportError,
    ) as error:
        sys.stderr.write(f"{prog}: {error}\n")
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
