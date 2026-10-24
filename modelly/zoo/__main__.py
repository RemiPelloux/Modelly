"""``modelly zoo``: list the zoo models, describe one, copy one into a new folder.

modelly zoo list                       every model with its field and summary
modelly zoo info age_seir              description, parameters, validation, references
modelly zoo copy age_seir my_epidemic  write model.py and README.md into my_epidemic/
"""

from __future__ import annotations

import argparse
import sys

from modelly.zoo.copy import copy_model, parameters
from modelly.zoo.registry import MODELS, ZooModel, get

PROG = "python -m modelly.zoo"
EXIT_OK = 0
EXIT_ERROR = 1


def build_parser(prog: str) -> argparse.ArgumentParser:
    """The ``list`` / ``info`` / ``copy`` parser."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Validated reference models to start from.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1],
    )
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="list the zoo models")
    listing.add_argument("--field", help="only the models of this field")
    info = commands.add_parser("info", help="describe one model")
    info.add_argument("name")
    copy = commands.add_parser("copy", help="copy a model into a new folder")
    copy.add_argument("name")
    copy.add_argument("directory")
    return parser


def list_models(field: str | None) -> str:
    """One line per model: name, field and summary."""
    chosen = [m for m in MODELS if field is None or m.field == field]
    width = max(len(m.name) for m in MODELS) + 2
    lines = [f"{m.name:<{width}}{m.field:<20}{m.summary}" for m in chosen]
    return "\n".join(lines)


def describe(entry: ZooModel) -> str:
    """The title, classes, parameters, validation and docstring of one model."""
    params = "\n".join(f"  {k} = {v!r}" for k, v in parameters(entry).items())
    return (
        f"{entry.title} ({entry.field})\n\n"
        f"from {entry.module} import {entry.model}, {entry.scenario}\n\n"
        f"Parameters ({entry.scenario}):\n{params}\n\n"
        f"Validation: {entry.validation}\n\n{entry.doc().strip()}"
    )


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run ``modelly zoo`` and return the exit status."""
    args = build_parser(prog).parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "list":
            text = list_models(args.field)
        elif args.command == "info":
            text = describe(get(args.name))
        else:
            written = copy_model(args.name, args.directory)
            text = "\n".join(f"wrote {path}" for path in written)
    except (KeyError, FileExistsError) as error:
        sys.stderr.write(f"{prog}: {error.args[0]}\n")
        return EXIT_ERROR
    sys.stdout.write(text + "\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
