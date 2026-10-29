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
"""


def inputs_from(args: argparse.Namespace) -> dict[str, Any]:
    """The ``StudioConfig`` fields the input options set."""
    return {
        "results": args.results,
        "observations": args.observations,
        "analysis": args.analysis,
    }


__all__ = ["INPUT_OPTIONS", "INPUT_PANELS", "inputs_from"]
