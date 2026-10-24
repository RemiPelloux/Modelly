"""Jupyter and IPython magics: ``%load_ext modelly.ipython``, then ``%modelly lint|profile``.

    %modelly lint model.py agents.py           the findings of python -m modelly.lint
    %modelly lint --fix model.py               any option of the command line works
    %modelly profile MyModel --steps 50        a Model class defined in the notebook
    %modelly profile model.py:MyModel --steps 50

The magics run the same code as the command line and print the same report. IPython is
never imported here: the shell that loads the extension is IPython, so ``import modelly``
never needs it.
"""

from __future__ import annotations

import shlex
import sys
from typing import Any

from modelly.core.model import Model

USAGE = """\
usage: %modelly lint [options] PATH [PATH ...]
       %modelly profile TARGET [--steps N] [options]
TARGET is a Model class of this notebook, path/to/model.py:Class or package.module:Class.
%modelly lint --help and %modelly profile --help list the options."""
QUOTES = "\"'"


def split(line: str) -> list[str]:
    """The words of a magic line; quotes group words, backslashes stay (Windows paths)."""
    return [word.strip(QUOTES) for word in shlex.split(line, posix=False)]


def notebook_class(target: str, namespace: dict[str, Any]) -> type[Model] | None:
    """The Model subclass named ``target`` in the notebook, when it is one."""
    value = namespace.get(target)
    if isinstance(value, type) and issubclass(value, Model):
        return value
    return None


def lint(argv: list[str]) -> int:
    """Run ``modelly lint`` with ``argv``; its exit status."""
    from modelly.lint.__main__ import main  # noqa: PLC0415 (loaded on use)

    return main(argv, prog="%modelly lint")


def profile(argv: list[str], namespace: dict[str, Any]) -> int:
    """Run ``modelly profile`` with ``argv``; a notebook class is used as the target."""
    from modelly.profile.__main__ import main, parse_args  # noqa: PLC0415 (on use)

    prog = "%modelly profile"
    target = parse_args(argv, prog).target
    return main(argv, prog=prog, cls=notebook_class(target, namespace))


def run_magic(line: str, namespace: dict[str, Any]) -> int | None:
    """Dispatch one ``%modelly`` line; print the usage when it names no command."""
    words = split(line)
    command, argv = (words[0], words[1:]) if words else ("", [])
    try:
        if command == "lint":
            return lint(argv)
        if command == "profile":
            return profile(argv, namespace)
    except SystemExit as stop:  # --help, or argparse rejecting the options
        return stop.code if isinstance(stop.code, int) else None
    sys.stdout.write(USAGE + "\n")
    return None


def load_ipython_extension(ipython: Any) -> None:
    """Register ``%modelly`` with an IPython shell (``%load_ext modelly.ipython``).

    IPython calls this with its running shell, so nothing here imports IPython.
    """

    def modelly(line: str) -> None:
        """%modelly lint PATH... | %modelly profile TARGET --steps N: see %modelly."""
        run_magic(line, ipython.user_ns)

    ipython.register_magic_function(modelly, "line", "modelly")
