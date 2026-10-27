"""Command line for ``modelly new``; exits 2 on a bad name, template or a used folder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from modelly.new import TEMPLATES, ProjectError, create_project

EXIT_CLEAN = 0
EXIT_USAGE = 2
PROG = "python -m modelly.new"
DEFAULT_TEMPLATE = "grid"

DESCRIPTION = """\
Write a new model project: a package with a seeded Scenario, an agent and a model, a
determinism test (same seed, same data), [tool.modelly.lint] settings, a README with an
ODD outline and a .gitignore. The project passes its own test and `modelly lint`."""

EPILOG = f"""\
examples:
  modelly new forest-fire                       the grid template, in ./forest-fire
  modelly new epidemic --template network       another template
  modelly new --list-templates                  what each template models
  modelly new traffic --from-zoo nagel_schreckenberg   start from a validated zoo model

exit status:
  {EXIT_CLEAN}  the project was written
  {EXIT_USAGE}  usage error: bad name, unknown template or zoo model, or the folder exists and is not empty"""

NEXT_STEPS = """\
created {count} files in {target}
next:
  cd {target}
  python -m pip install -e ".[dev]"
  python -m pytest
  python -m modelly lint {package}
"""


def build_parser(prog: str = PROG) -> argparse.ArgumentParser:
    """The argument parser, with examples and exit codes in its help."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", nargs="?", help="the project folder to create")
    parser.add_argument(
        "--template",
        choices=sorted(TEMPLATES),
        default=DEFAULT_TEMPLATE,
        help=f"what the model starts from (default: {DEFAULT_TEMPLATE})",
    )
    parser.add_argument(
        "--from-zoo",
        metavar="MODEL",
        help="start from a validated zoo model instead of a template (modelly zoo list)",
    )
    parser.add_argument(
        "--list-templates", action="store_true", help="print the templates and exit"
    )
    return parser


def write(args: argparse.Namespace) -> list[Path]:
    """The files of the new project: a zoo model's copy, or a template's project."""
    if args.from_zoo:
        from modelly.zoo import copy_model  # noqa: PLC0415 - only this option needs the zoo

        return copy_model(args.from_zoo, args.name)
    return create_project(args.name, args.template)


def list_templates() -> str:
    """One line per template: name and summary."""
    width = max(map(len, TEMPLATES)) + 2
    return "\n".join(f"{name:<{width}}{t.summary}" for name, t in TEMPLATES.items())


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Write the project and return the exit status; ``prog`` names the command in --help."""
    parser = build_parser(prog)
    args = parser.parse_args(argv)
    if args.list_templates:
        sys.stdout.write(list_templates() + "\n")
        return EXIT_CLEAN
    if not args.name:
        parser.error("the project name is required (or --list-templates)")
    try:
        written = write(args)
    except (ProjectError, OSError, KeyError) as error:
        sys.stderr.write(f"modelly new: {error}\n")
        return EXIT_USAGE
    if args.from_zoo:
        sys.stdout.write("".join(f"wrote {path}\n" for path in written))
        return EXIT_CLEAN
    package = written[0].parent.name  # the template's first file is in the package
    sys.stdout.write(
        NEXT_STEPS.format(count=len(written), target=args.name, package=package)
    )
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
