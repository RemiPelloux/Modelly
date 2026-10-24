"""Command line for ``python -m modelly.profile``: run a model under the profiler and report."""

from __future__ import annotations

import argparse
import json
import sys
import traceback

from modelly.profile.loader import (
    SIZE_PARAMS,
    TargetError,
    build_model,
    load_class,
    parse_param,
    size_param,
)
from modelly.profile.profiler import DEFAULT_TOP, Profiler
from modelly.profile.sizes import (
    DEFAULT_STEPS,
    MIN_SIZES,
    SizeComparison,
    compare_sizes,
)

EXIT_OK, EXIT_MODEL_ERROR, EXIT_USAGE = 0, 1, 2
GUIDE = "https://remipelloux.github.io/Modelly/profile.html"
PROG = "python -m modelly.profile"

DESCRIPTION = """\
Run a Modelly model for a number of steps and report where each step's time
goes: every AgentSet.do / shuffle_do / map call by agent class and method
(calls, agents per call, microseconds per agent), DataCollector.collect, the
scheduled-event callbacks, and births and deaths per step. When a pattern is
evident the report ends with hints pointing at `python -m modelly.lint` codes.

The model is built with its parameters: those its constructor takes by name
go to it, the others to its Scenario (the class its `scenario` argument
defaults to). --seed goes to that Scenario, or to `rng` when there is none.

With --sizes the model is built and profiled once per size and the report
compares microseconds per agent side by side: when they grow with N, each
agent probably scans the population (MDL101 / MDL102).
"""

EPILOG = f"""\
examples:
  python -m modelly.profile my_model.py:MyModel --steps 200
  python -m modelly.profile my_model.py:MyModel --param n=5000 --param width=100
  python -m modelly.profile modelly.examples.advanced.wolf_sheep.model:WolfSheep \\
      --seed 42 --top 5
  python -m modelly.profile my_model.py:MyModel --format csv > profile.csv
  python -m modelly.profile my_model.py:MyModel --sample-every 10 --steps 1000
  python -m modelly.profile my_model.py:MyModel --sizes 1000,4000 --steps 20
  python -m modelly.profile my_model.py:MyModel --sizes 500,2000 --size-param initial_sheep

output formats:
  text  the table of the costliest operations, then the hints (default)
  json  totals per operation, per-step totals and hints
  csv   one row per step and per operation within it (Profiler.to_dataframe)
  with --sizes: json and csv hold us per agent by operation and size

exit codes:
  0  the model ran and the report was written
  1  the model raised while being built or run (traceback on stderr)
  2  bad command line, or the target cannot be found or built

guide: {GUIDE}
"""


def positive(text: str) -> int:
    """An integer of at least 1, for --steps and --sample-every."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {text}")
    return value


def size_list(text: str) -> list[int]:
    """At least two different positive integers, comma-separated, for --sizes."""
    values = sorted({positive(part) for part in text.split(",") if part.strip()})
    if len(values) < MIN_SIZES:
        raise argparse.ArgumentTypeError(
            f"expected at least {MIN_SIZES} different sizes, got {text}"
        )
    return values


OPTIONS = (
    (("target",), {"help": "path/to/model.py:Class or package.module:Class"}),
    (
        ("--steps",),
        {
            "type": positive,
            "default": DEFAULT_STEPS,
            "help": "steps to run (default: %(default)s)",
        },
    ),
    (
        ("--param",),
        {
            "action": "append",
            "default": [],
            "metavar": "KEY=VALUE",
            "help": "a model or scenario parameter, as a Python literal; repeatable",
        },
    ),
    (("--seed",), {"type": int, "help": "seed for the model's generators"}),
    (("--format",), {"choices": ("text", "json", "csv"), "default": "text"}),
    (
        ("--top",),
        {
            "type": positive,
            "default": DEFAULT_TOP,
            "help": "rows in the text table (default: %(default)s)",
        },
    ),
    (
        ("--sample-every",),
        {
            "type": positive,
            "default": 1,
            "metavar": "N",
            "help": "profile one step in N (default: 1)",
        },
    ),
    (
        ("--sizes",),
        {
            "type": size_list,
            "metavar": "N1,N2,...",
            "help": "build and profile the model at each population size and compare",
        },
    ),
    (
        ("--size-param",),
        {
            "metavar": "NAME",
            "help": f"the parameter --sizes sets (default: the first of {', '.join(SIZE_PARAMS)} taken)",
        },
    ),
)


def parse_args(argv: list[str] | None, prog: str = PROG) -> argparse.Namespace:
    """Read the command line; ``prog`` names the command in --help."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    for flags, options in OPTIONS:
        parser.add_argument(*flags, **options)
    return parser.parse_args(argv)


def render(prof: Profiler | SizeComparison, args: argparse.Namespace) -> str:
    """The report in the requested format."""
    if args.format == "json":
        return json.dumps(prof.to_dict(), indent=2)
    if args.format == "csv":
        return prof.to_dataframe().to_csv(index=False).rstrip("\n")
    return prof.report(top=args.top)


def profile(args: argparse.Namespace) -> Profiler | SizeComparison:
    """Build the model and profile it, once per size with --sizes."""
    params = dict(parse_param(text) for text in args.param)
    cls = load_class(args.target)
    if args.sizes:
        name = size_param(cls, args.size_param)
        return compare_sizes(
            lambda size: build_model(cls, {**params, name: size}, args.seed),
            args.sizes,
            args.steps,
            args.sample_every,
        )
    model = build_model(cls, params, args.seed)
    with Profiler(model, sample_every=args.sample_every) as prof:
        model.run_for(args.steps)
    return prof


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Build the model, run it under the profiler and write the report; the exit status."""
    args = parse_args(argv, prog)
    try:
        prof = profile(args)
    except TargetError as error:
        sys.stderr.write(f"modelly.profile: {error}\n")
        return EXIT_USAGE
    except Exception:  # any model error is reported, not raised
        traceback.print_exc()
        return EXIT_MODEL_ERROR
    sys.stdout.write(render(prof, args) + "\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
