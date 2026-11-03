"""The ``modelly studio`` options for the Experiments, Assimilation and Analysis tabs.

They name the tabs' inputs: a results store, an observations file and an analysis function.
"""

from __future__ import annotations

import argparse
from typing import Any

INPUT_OPTIONS = (
    (
        ("--results",),
        {
            "metavar": "DIR",
            "help": "an experiment's results store, for the Experiments tab",
        },
    ),
    (
        ("--observations",),
        {
            "metavar": "FILE.csv",
            "help": "observations (a time column, one column per reporter) to assimilate",
        },
    ),
    (
        ("--no-code",),
        {
            "action": "store_true",
            "help": "only the tabs for people who do not write code (compare, card, builder)",
        },
    ),
    (
        ("--classroom",),
        {
            "metavar": "DIR",
            "help": "a folder shared by a class: shared parameters and submitted runs",
        },
    ),
    (
        ("--language",),
        {
            "default": "en",
            "help": "the language of Studio's labels: en, es, fr, pt, zh (default: %(default)s)",
        },
    ),
    (
        ("--hub",),
        {
            "metavar": "NAME",
            "help": "open a model of the hub by name instead of a target (installed first)",
        },
    ),
    (
        ("--analysis",),
        {
            "metavar": "FILE.py:FUNCTION",
            "help": "a function returning posteriors or sensitivity results to show",
        },
    ),
)

INPUT_PANELS = """\
  map            the space drawn by WebGL in the browser, for large models
  ensemble       bands of the reporters across replicates
  assimilation   particle filter or ensemble Kalman filter on --observations
  experiments    the runs of --results, filtered, an output against a parameter
  analysis       posteriors and sensitivity results from --analysis
  compare        one parameter varied, the scenarios ranked on paired replicates
  card           the model card
  builder        a model from a form, its code to read and download
  classroom      with --classroom: submit runs, share parameters, see the class's runs
"""


def inputs_from(args: argparse.Namespace) -> dict[str, Any]:
    """The ``StudioConfig`` fields the input options set."""
    return {
        "results": args.results,
        "observations": args.observations,
        "analysis": args.analysis,
        "mode": "no-code" if args.no_code else "full",
        "language": args.language,
        "classroom": args.classroom,
    }


def target_from(args: argparse.Namespace) -> str:
    """The target: the positional one, or the hub model ``--hub`` names.

    Raises:
        SystemExit: (from argparse) with neither, or with both.
    """
    if bool(args.target) == bool(args.hub):
        raise argparse.ArgumentTypeError(
            "give a target or --hub NAME, not both or neither"
        )
    if args.target:
        return str(args.target)
    from modelly.hub import load  # noqa: PLC0415

    return load().get(args.hub).target


__all__ = ["INPUT_OPTIONS", "INPUT_PANELS", "inputs_from", "target_from"]
