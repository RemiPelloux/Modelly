"""Command line for ``python -m modelly.sensitivity`` (``modelly sensitivity``)."""

from __future__ import annotations

import argparse
import sys
import tomllib

from modelly.calibrate.simulator import SimulationError
from modelly.experiments.executors import available_executors
from modelly.experiments.spec import SpecError
from modelly.experiments.store import StoreMismatchError
from modelly.profile.loader import TargetError
from modelly.sensitivity.spec import METHODS, load_sensitivity

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
GUIDE = "https://remipelloux.github.io/Modelly/sensitivity.html"
PROG = "python -m modelly.sensitivity"

DESCRIPTION = """\
Rank the parameters of a model by their influence on one output, as described
in a TOML file: the model, steps and replicates ([experiment]), the parameter
ranges ([space]) and the method ([sensitivity]: one-at-a-time, Morris
elementary effects, Sobol indices with bootstrap intervals, or PAWN). Prints
the ranking, most influential first; the same seed gives the same numbers on
every executor."""

EPILOG = f"""\
examples:
  modelly sensitivity sir.toml
  modelly sensitivity sir.toml --method sobol --executor processes
  modelly sensitivity sir.toml --output ranking.csv

a minimal spec:
  [experiment]
  model = "model.py:SIR"
  steps = 60
  outputs = ["infected"]
  [space]
  beta = {{ min = 0.1, max = 0.8 }}
  gamma = {{ min = 0.05, max = 0.3 }}
  [sensitivity]
  method = "morris"
  statistic = "max"
  trajectories = 20

methods: {", ".join(sorted(METHODS))}
executors: {", ".join(available_executors())}

exit codes:
  {EXIT_OK}  the analysis finished
  {EXIT_FAILED}  a model run failed
  {EXIT_USAGE}  bad command line, unreadable spec, or a store of another analysis

guide: {GUIDE}"""


def build_parser(prog: str = PROG) -> argparse.ArgumentParser:
    """The parser: the spec and the overrides."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("spec", help="the analysis's TOML file")
    parser.add_argument("--method", choices=sorted(METHODS), help="override the method")
    parser.add_argument("--executor", help="override [run] executor")
    parser.add_argument("--max-parallel", type=int, help="override [run] max_parallel")
    parser.add_argument("--output", help="write the ranked table to this CSV file")
    return parser


def _analyse(args: argparse.Namespace) -> int:
    """Run the analysis and write its ranking; the exit status."""
    method, arguments = load_sensitivity(args.spec, args.method)
    if args.executor is not None:
        arguments["executor"] = args.executor
    if args.max_parallel is not None:
        arguments["max_parallel"] = args.max_parallel
    result = method(**arguments)
    ranking = result.ranking()
    sys.stdout.write(f"{result.method} (ranked by {result.measure})\n")
    sys.stdout.write(f"{ranking.to_string()}\n")
    if args.output is not None:
        ranking.rename_axis("parameter").to_csv(args.output, encoding="utf-8")
        sys.stdout.write(f"table: {args.output}\n")
    return EXIT_OK


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run the command line; the exit status."""
    args = build_parser(prog).parse_args(argv)
    try:
        return _analyse(args)
    except SimulationError as error:
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
