"""Command line for ``python -m modelly.calibrate`` (``modelly calibrate``)."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from modelly.calibrate.base import Calibration, CalibrationError
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.simulator import SimulationError
from modelly.calibrate.smc import ABCSMC
from modelly.calibrate.spec import METHODS, load_calibration
from modelly.experiments.executors import available_executors
from modelly.experiments.spec import SpecError
from modelly.experiments.store import StoreMismatchError
from modelly.profile.loader import TargetError

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
GUIDE = "https://remipelloux.github.io/Modelly/calibration.html"
PROG = "python -m modelly.calibrate"

DESCRIPTION = """\
Fit a model's parameters to observed data, as described in a TOML file: the
model and fixed parameters ([experiment], [space]), the priors ([space] ranges
and choices, or [priors]), the observed targets ([[targets]]) and the method
([calibration]: ABC-SMC, ABC rejection, simulated moments or Bayesian
optimisation). Prints the posterior summary (mean, median, sd, HDI); the same
seed gives the same posterior on every executor."""

EPILOG = f"""\
examples:
  modelly calibrate sir.toml
  modelly calibrate sir.toml --executor processes --max-parallel 8
  modelly calibrate sir.toml --output posterior.csv        # every sample, weighted
  modelly calibrate sir.toml --checkpoint sir.ckpt         # resumable (abc_smc)

a minimal spec:
  [experiment]
  model = "model.py:SIR"
  steps = 40
  seed = 7
  [space]
  beta = {{ min = 0.05, max = 1.0 }}
  gamma = {{ min = 0.02, max = 0.5 }}
  population = 1000
  [[targets]]
  name = "infected"
  file = "cases.csv"
  column = "cases"
  [calibration]
  method = "abc_smc"
  particles = 100
  budget = 3000

methods: {", ".join(sorted(METHODS))}
executors: {", ".join(available_executors())}

exit codes:
  {EXIT_OK}  the calibration finished
  {EXIT_FAILED}  a run failed or no sample was accepted
  {EXIT_USAGE}  bad command line, unreadable spec, or a store of another calibration

guide: {GUIDE}"""


def build_parser(prog: str = PROG) -> argparse.ArgumentParser:
    """The parser: the spec, executor overrides, output and checkpoint files."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("spec", help="the calibration's TOML file")
    parser.add_argument("--executor", help="override [run] executor")
    parser.add_argument("--max-parallel", type=int, help="override [run] max_parallel")
    parser.add_argument(
        "--output", help="write every posterior sample to this CSV file"
    )
    parser.add_argument(
        "--checkpoint",
        help="abc_smc: save after every generation; resume from it when it exists",
    )
    return parser


def _calibrate(args: argparse.Namespace) -> int:
    """Load (or resume), run, and report; the exit status."""
    calibration, run, settings = load_calibration(args.spec)
    checkpoint = args.checkpoint
    if checkpoint is not None and not isinstance(calibration, ABCSMC):
        raise SpecError("--checkpoint needs method = 'abc_smc'")
    if checkpoint is not None:
        run["checkpoint"] = checkpoint
        if Path(checkpoint).is_file():
            calibration = ABCSMC.load(checkpoint)
    run |= {"executor": args.executor or settings.executor}
    run |= {"max_parallel": args.max_parallel or settings.max_parallel}
    posterior = calibration.run(**run, **settings.options)
    _report(calibration, posterior, args.output)
    return EXIT_OK


def _report(calibration: Calibration, posterior: Posterior, output: str | None) -> None:
    """Write the summary and the run's diagnostics; the samples to ``output``."""
    sys.stdout.write(f"{posterior!r}\n{posterior.summary().to_string()}\n")
    info = ", ".join(f"{key}={value}" for key, value in posterior.info.items())
    sys.stdout.write(f"{calibration.method}: {info}\n")
    if output is not None:
        posterior.to_dataframe().to_csv(output, index=False, encoding="utf-8")
        sys.stdout.write(f"samples: {output}\n")


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run the command line; the exit status."""
    args = build_parser(prog).parse_args(argv)
    try:
        return _calibrate(args)
    except (CalibrationError, SimulationError) as error:
        sys.stderr.write(f"{prog}: {error}\n")
        return EXIT_FAILED
    except (
        OSError,
        KeyError,
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
