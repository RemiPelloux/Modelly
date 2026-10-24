"""``python -m modelly`` (or the ``modelly`` script): one entry point for the command-line tools.

``modelly lint src/`` runs ``python -m modelly.lint src/``; each command keeps its own
``--help`` and exit status. A new tool is one line in ``COMMANDS``: its name, the module
whose ``main(argv) -> int`` runs it, and a one-line summary.
"""

from __future__ import annotations

import argparse
import importlib
import sys

import modelly

EXIT_USAGE = 2

# (name, module with main(argv) -> int, one-line summary)
COMMANDS = (
    (
        "lint",
        "modelly.lint.__main__",
        "find reproducibility bugs and O(N^2) patterns in a model",
    ),
    (
        "migrate",
        "modelly.migrate",
        "rewrite a Mesa model for Modelly and report what is left",
    ),
    (
        "profile",
        "modelly.profile.__main__",
        "time a model's steps by agent class, data collection and events",
    ),
)

DESCRIPTION = "Command-line tools for Modelly models."

EPILOG_TEMPLATE = """\
commands:
{commands}

examples:
  modelly lint src/                     check a model (same as python -m modelly.lint src/)
  modelly lint --explain MDL101         why a rule matters, with a fix
  modelly migrate my_mesa_model/        dry run of the Mesa codemod
  modelly profile model.py:MyModel      where each step's time goes
  modelly COMMAND --help                every option of one command

exit status:
  the command's own (see its --help); {usage} for an unknown command or no command"""


def build_parser() -> argparse.ArgumentParser:
    """The top-level parser: the command list, --version and --help."""
    width = max(len(name) for name, _, _ in COMMANDS) + 2
    commands = "\n".join(f"  {name:<{width}}{summary}" for name, _, summary in COMMANDS)
    parser = argparse.ArgumentParser(
        prog="modelly",
        description=DESCRIPTION,
        epilog=EPILOG_TEMPLATE.format(commands=commands, usage=EXIT_USAGE),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"modelly {modelly.__version__}"
    )
    parser.add_argument(
        "command", choices=[name for name, _, _ in COMMANDS], help="the tool to run"
    )
    parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="its arguments (modelly COMMAND --help)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command named by the first argument and return its exit status."""
    argv = sys.argv[1:] if argv is None else argv
    modules = {name: module for name, module, _ in COMMANDS}
    if argv and argv[0] in modules:
        return importlib.import_module(modules[argv[0]]).main(argv[1:])
    # Prints the help or the version and exits, or rejects the command (exit 2).
    build_parser().parse_args(argv)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
