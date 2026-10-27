"""Command line for ``modelly export-web``: write a static site that runs a model in a browser."""

from __future__ import annotations

import sys
from pathlib import Path

from modelly.profile.loader import TargetError
from modelly.provenance.commands.common import (
    EXIT_OK,
    EXIT_USAGE,
    add_options,
    error,
    make_parser,
    positive,
)
from modelly.studio.config import DEFAULT_SEED
from modelly.web.export import DEFAULT_STEPS, PYODIDE_URL, WebExport, export_web
from modelly.web.packages import ModelRunError

PROG = "python -m modelly.web"
GUIDE = "https://remipelloux.github.io/Modelly/browser.html"
EXIT_MODEL_ERROR = 1

DESCRIPTION = """\
Write a static site that runs a model in the browser with Pyodide: no
installation, no server code. Open it from any static host (GitHub Pages, a
docs build, python -m http.server); browsers do not run it from file://.

The page builds the parameter panel from the model's Scenario, as Studio does,
runs the model in a Web Worker (the page stays responsive during long runs),
plots its numeric model reporters and draws the agents in space. Pyodide comes
from its CDN at a pinned version; the site ships Modelly as a pure-Python wheel
and the model's code. The export runs the model for --steps steps first, to
check it and to find the packages it imports: only those are downloaded.
"""

EPILOG = f"""\
examples:
  modelly export-web model.py:Epidemic --out site/
  modelly export-web modelly.zoo.forest_fire.model:ForestFire --out fire/ --steps 50
  modelly export-web modelly.examples.basic.schelling.model:Schelling --out schelling/
  modelly export-web model.py:Epidemic --out site/ --wheel dist/modelly_abm-*-wasm32.whl

exit codes:
  0  the site was written
  1  the model failed to build or run for --steps steps
  2  bad command line, or the model cannot be found

guide: {GUIDE}
"""

OPTIONS = (
    (("target",), {"help": "path/to/model.py:Class or package.module:Class"}),
    (("--out",), {"type": Path, "default": Path("site"), "help": "site folder"}),
    (
        ("--steps",),
        {"type": positive, "default": DEFAULT_STEPS, "help": "steps of the check run"},
    ),
    (("--seed",), {"type": int, "default": DEFAULT_SEED, "help": "default seed"}),
    (("--title",), {"default": "", "help": "page title (default: the class name)"}),
    (("--wheel",), {"type": Path, "help": "ship this Modelly wheel instead"}),
    (("--pyodide-url",), {"default": PYODIDE_URL, "help": "Pyodide base URL"}),
    (
        ("--package",),
        {"action": "append", "default": [], "help": "also load this Pyodide package"},
    ),
    (
        ("--skip-package",),
        {"action": "append", "default": [], "help": "do not load this package"},
    ),
)


def _options(args) -> WebExport:
    """The export the parsed command line asks for."""
    return WebExport(
        target=args.target,
        out=args.out,
        steps=args.steps,
        seed=args.seed,
        title=args.title,
        wheel=args.wheel,
        pyodide_url=args.pyodide_url,
        add_packages=tuple(args.package),
        skip_packages=tuple(args.skip_package),
    )


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Export the model's site; the exit status."""
    parser = make_parser(prog, DESCRIPTION, EPILOG)
    add_options(parser, OPTIONS)
    args = parser.parse_args(argv)
    if args.wheel is not None and not args.wheel.is_file():
        error(prog, f"no such wheel: {args.wheel}")
        return EXIT_USAGE
    try:
        manifest = export_web(_options(args))
    except ModelRunError as problem:
        error(prog, problem)
        return EXIT_MODEL_ERROR
    except TargetError as problem:
        error(prog, problem)
        return EXIT_USAGE
    sys.stdout.write(
        f"wrote {args.out}/ ({manifest['target']}; packages: "
        f"{', '.join(manifest['packages'])})\n"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
