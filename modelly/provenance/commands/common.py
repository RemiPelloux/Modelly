"""Pieces the provenance command lines share: parser, exit codes, model options."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

GUIDE = "https://remipelloux.github.io/Modelly/provenance.html"
EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_MODEL_ERROR = 0, 1, 2, 3

MODEL_OPTIONS = (
    (("target",), {"help": "path/to/model.py:Class or package.module:Class"}),
    (
        ("--scenario",),
        {
            "type": Path,
            "metavar": "FILE",
            "help": "TOML file of scenario parameters (a flat table; 'seed' is the seed)",
        },
    ),
    (
        ("--param",),
        {
            "action": "append",
            "default": [],
            "metavar": "KEY=VALUE",
            "help": "a model or scenario parameter, as a Python literal; repeatable, "
            "overrides --scenario",
        },
    ),
    (("--seed",), {"type": int, "help": "seed for the model's generators"}),
)


def make_parser(prog: str, description: str, epilog: str) -> argparse.ArgumentParser:
    """A parser that keeps the layout of the description and the epilog."""
    return argparse.ArgumentParser(
        prog=prog,
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def add_options(parser: argparse.ArgumentParser, options: tuple[Any, ...]) -> None:
    """Add ``(flags, keyword arguments)`` pairs to ``parser``."""
    for flags, kwargs in options:
        parser.add_argument(*flags, **kwargs)


def positive(text: str) -> int:
    """An integer of at least 1."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {text}")
    return value


def non_negative(text: str) -> float:
    """A float of at least 0, for tolerances."""
    value = float(text)
    if not value >= 0:
        raise argparse.ArgumentTypeError(f"expected a number >= 0, got {text}")
    return value


def error(prog: str, message: object) -> None:
    """Write ``prog: message`` to stderr."""
    sys.stderr.write(f"{prog}: {message}\n")
