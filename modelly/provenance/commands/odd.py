"""``modelly odd``: write an ODD protocol skeleton of a model to stdout."""

from __future__ import annotations

import sys
import traceback

from modelly.profile.loader import TargetError, build_model, load_class, parse_param
from modelly.provenance.commands.common import (
    EXIT_MODEL_ERROR,
    EXIT_OK,
    EXIT_USAGE,
    GUIDE,
    MODEL_OPTIONS,
    add_options,
    error,
    make_parser,
)
from modelly.provenance.odd import odd_markdown
from modelly.provenance.runner import SEED_KEY, read_scenario

PROG = "python -m modelly.provenance.commands.odd"

DESCRIPTION = """\
Build a model (without running it) and write the skeleton of its ODD protocol
description (Overview, Design concepts, Details) as Markdown on stdout, with
the seven ODD elements:

  1. Purpose and patterns              the model class's docstring
  2. Entities, state variables, scales agent classes, their Column declarations
                                       and attributes, global variables, spaces
  3. Process overview and scheduling   the statements of step(), in order
  4. Design concepts                   the eleven concepts; Observation lists
                                       the DataCollector reporters
  5. Initialization                    scenario parameters and initial counts
  6. Input data                        to be written
  7. Submodels                         each agent method, scheduled ones first

Every place only the modeller can fill holds a TODO marker.
"""

EPILOG = f"""\
examples:
  modelly odd model.py:Epidemic > ODD.md
  modelly odd model.py:Epidemic --scenario scenario.toml --seed 1 > ODD.md
  modelly odd modelly.examples.basic.schelling.model:Schelling

exit codes:
  0  the skeleton was written
  2  bad command line, or the target or scenario cannot be used
  3  the model raised while being built (traceback on stderr)

guide: {GUIDE}
"""


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Build the model and print its ODD skeleton; the exit status."""
    parser = make_parser(prog, DESCRIPTION, EPILOG)
    add_options(parser, MODEL_OPTIONS)
    args = parser.parse_args(argv)
    try:
        params = {**read_scenario(args.scenario)}
        params.update(parse_param(text) for text in args.param)
        file_seed = params.pop(SEED_KEY, None)
        seed = args.seed if args.seed is not None else file_seed
        model = build_model(load_class(args.target), params, seed)
    except TargetError as problem:
        error(prog, problem)
        return EXIT_USAGE
    except Exception:  # any model error is reported, not raised
        traceback.print_exc()
        return EXIT_MODEL_ERROR
    sys.stdout.write(odd_markdown(model))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
