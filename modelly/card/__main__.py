"""``modelly card``: write, check, show and stamp model cards.

modelly card new model.py:Epidemic -o card.toml   a skeleton from the model's code
modelly card check card.toml                      complete, and validated on this source?
modelly card check --zoo                          every zoo model's card
modelly card show age_seir                        a card as Markdown (a path or a zoo name)
modelly card stamp card.toml --root .             run its validation tests; stamp on success
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from modelly.card.freshness import problems, stamp
from modelly.card.render import card_markdown, card_skeleton
from modelly.card.schema import CardError, read_card, write_card

PROG = "python -m modelly.card"
EXIT_OK, EXIT_PROBLEMS, EXIT_USAGE = 0, 1, 2
CARD_FILE = "card.toml"


def _say(text: object, stream=None) -> None:
    """One line on stdout, or on ``stream``."""
    (stream or sys.stdout).write(f"{text}\n")


def build_parser(prog: str) -> argparse.ArgumentParser:
    """The ``new`` / ``check`` / ``show`` / ``stamp`` parser."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Model cards: what a model is for, how it was validated, its limits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1] + "\nguide: docs/model_cards.md",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="write a card skeleton for a model")
    new.add_argument("target", help="path/to/model.py:Class or package.module:Class")
    new.add_argument("-o", "--output", default=CARD_FILE, type=Path)
    new.add_argument("--name", help="the card's name (default: the class name)")
    check = commands.add_parser("check", help="report incomplete or stale cards")
    check.add_argument("cards", nargs="*", type=Path)
    check.add_argument(
        "--zoo", action="store_true", help="check every zoo model's card"
    )
    show = commands.add_parser("show", help="print a card as Markdown")
    show.add_argument("card", help="a card.toml path or a zoo model name")
    run = commands.add_parser("stamp", help="run the validation tests, then stamp")
    run.add_argument("card", type=Path)
    run.add_argument("--root", type=Path, default=Path(), help="where the tests run")
    return parser


def resolve(text: str | Path) -> Path:
    """A card path: ``text`` itself, or the card of the zoo model it names."""
    path = Path(text)
    if path.exists() or path.suffix:
        return path
    from modelly.zoo.registry import get  # noqa: PLC0415 - only for zoo names

    return get(str(text)).card


def _new(args: argparse.Namespace) -> int:
    """Write a skeleton; refuse to overwrite a card."""
    from modelly.profile.loader import TargetError, load_class  # noqa: PLC0415

    if args.output.exists():
        _say(f"{args.output} exists; not overwritten", sys.stderr)
        return EXIT_USAGE
    try:
        model_class = load_class(args.target)
    except TargetError as problem:
        _say(problem, sys.stderr)
        return EXIT_USAGE
    card = card_skeleton(model_class, args.name)
    if args.target.rpartition(":")[0].endswith(".py"):
        card = replace(card, model=args.target)
    write_card(card, args.output)
    _say(
        f"wrote {args.output}: fill the TODOs, then `modelly card stamp {args.output}`"
    )
    return EXIT_OK


def _check(args: argparse.Namespace) -> int:
    """Print every problem of every card; non-zero when there is one."""
    from modelly.zoo.registry import MODELS  # noqa: PLC0415

    paths = list(args.cards) + ([m.card for m in MODELS] if args.zoo else [])
    paths = paths or [Path(CARD_FILE)]
    status = EXIT_OK
    for path in paths:
        try:
            found = problems(read_card(path), path.parent)
        except CardError as problem:
            found = [str(problem)]
        for line in found:
            _say(f"{path}: {line}")
        status = status if not found else EXIT_PROBLEMS
    if status == EXIT_OK:
        _say(f"{len(paths)} card(s) complete and validated on the current source")
    return status


def _stamp(args: argparse.Namespace) -> int:
    """Run the tests; stamp the card when they pass."""
    passed, output = stamp(args.card, args.root)
    _say(output.rstrip())
    _say(f"{args.card}: {'stamped' if passed else 'validation failed, not stamped'}")
    return EXIT_OK if passed else EXIT_PROBLEMS


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run ``modelly card`` and return the exit status."""
    args = build_parser(prog).parse_args(argv)
    try:
        if args.command == "new":
            return _new(args)
        if args.command == "check":
            return _check(args)
        if args.command == "stamp":
            return _stamp(args)
        sys.stdout.write(card_markdown(read_card(resolve(args.card))))
    except (CardError, KeyError) as problem:
        _say(problem, sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
