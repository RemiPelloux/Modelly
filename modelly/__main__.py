"""``python -m modelly`` (or the ``modelly`` script): one entry point for the command-line tools.

``modelly lint src/`` runs ``python -m modelly.lint src/``; each command keeps its own
``--help`` and exit status. A new tool is one line in ``COMMANDS``: its name, the module
whose ``main(argv, prog) -> int`` runs it, and a one-line summary. ``prog`` is
``modelly NAME``, so the command's --help names it the way it was run.
"""

from __future__ import annotations

import argparse
import importlib
import sys

import modelly

EXIT_USAGE = 2

# (name, module with main(argv, prog) -> int, one-line summary)
COMMANDS = (
    (
        "experiment",
        "modelly.experiments.__main__",
        "run a parameter sweep from a TOML spec; resumable, on any executor",
    ),
    (
        "bench",
        "modelly.bench.__main__",
        "run the benchmark playbooks, keep a history and report regressions",
    ),
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
        "new",
        "modelly.new.__main__",
        "write a new model project from a template, seeded, tested and linted",
    ),
    (
        "profile",
        "modelly.profile.__main__",
        "time a model's steps by agent class, data collection and events",
    ),
    (
        "run",
        "modelly.provenance.commands.run",
        "run a model once; write its outputs and a provenance manifest",
    ),
    (
        "verify",
        "modelly.provenance.commands.verify",
        "rerun a manifest and report the first output that differs",
    ),
    (
        "bundle",
        "modelly.provenance.commands.bundle",
        "pack a run into a deterministic zip for archiving (Zenodo)",
    ),
    (
        "odd",
        "modelly.provenance.commands.odd",
        "write an ODD protocol skeleton of a model",
    ),
    (
        "zoo",
        "modelly.zoo.__main__",
        "list, describe and copy the validated reference models",
    ),
)

DESCRIPTION = "Command-line tools for Modelly models."

EPILOG_TEMPLATE = """\
commands:
{commands}

examples:
  modelly experiment run study.toml     run a sweep (resumes where it stopped)
  modelly lint src/                    check a model (same as python -m modelly.lint src/)
  modelly lint --explain MDL101         why a rule matters, with a fix
  modelly migrate my_mesa_model/        dry run of the Mesa codemod
  modelly new my-model --template grid  a new project, tested and linted
  modelly profile model.py:MyModel      where each step's time goes
  modelly run model.py:MyModel --steps 100 --seed 1 --out runs/
                                        outputs and runs/manifest.json
  modelly verify runs/manifest.json     rerun and compare the outputs
  modelly bundle runs/ --out study.zip  code, lock file, seeds and outputs
  modelly odd model.py:MyModel > ODD.md ODD protocol skeleton
  modelly bench --label v1.3.0          time the playbooks, append to the history
  modelly zoo copy age_seir my_model/   start a project from a zoo model
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
        command = importlib.import_module(modules[argv[0]])
        return command.main(argv[1:], prog=f"modelly {argv[0]}")
    # Prints the help or the version and exits, or rejects the command (exit 2).
    build_parser().parse_args(argv)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
