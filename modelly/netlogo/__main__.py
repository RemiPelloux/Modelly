"""Command line for ``python -m modelly.netlogo``; exit 1 when lines were not translated."""

from __future__ import annotations

import argparse
import sys
from importlib.resources import files
from pathlib import Path

from modelly.netlogo._translate import Translation, translate

__all__ = ["main"]

EXIT_CLEAN = 0
EXIT_UNTRANSLATED = 1
EXIT_USAGE = 2
PROG = "python -m modelly.netlogo"
SUFFIX = ".nlogo"
EXAMPLES = ("fire", "wolf_sheep")

DESCRIPTION = """\
Translate a NetLogo model (.nlogo) into a runnable Modelly model.

The code tab becomes a model class whose methods are the procedures; the sliders and
switches become Scenario fields. Lines outside the supported subset are kept as
`# NETLOGO` comments in the output and listed on stderr, so nothing is dropped
silently."""

EPILOG = f"""\
examples:
  python -m modelly.netlogo fire.nlogo -o fire.py       translate a model to a file
  python -m modelly.netlogo model.nlogo                 print the Python on stdout
  python -m modelly.netlogo --example wolf_sheep -o wolf_sheep.py
                                                        a bundled model ({", ".join(EXAMPLES)})
  python -m modelly.netlogo --example fire --show       print the bundled NetLogo source

exit status:
  {EXIT_CLEAN}  every line was translated (display-only lines may have been dropped)
  {EXIT_UNTRANSLATED}  some lines were not translated: the output marks them NETLOGO
  {EXIT_USAGE}  usage error: no input, an unreadable file, or an unknown example

the subset and its semantics: docs/netlogo.md"""


def build_parser(prog: str = PROG) -> argparse.ArgumentParser:
    """The argument parser, with examples and exit codes in its help."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("model", nargs="?", help="the .nlogo file to translate")
    parser.add_argument(
        "-o", "--output", help="write the Python here (default: stdout)"
    )
    parser.add_argument(
        "--name", help="the stem of the class names (default: the file's)"
    )
    parser.add_argument("--example", choices=EXAMPLES, help="translate a bundled model")
    parser.add_argument(
        "--show",
        action="store_true",
        help="print the NetLogo source instead of translating",
    )
    return parser


def read_source(args: argparse.Namespace) -> tuple[str, str, str]:
    """The NetLogo text, the class-name stem and the name used in the report.

    Raises:
        OSError: when the file cannot be read.
        ValueError: when neither a file nor an example is given.
    """
    if args.example:
        resource = files("modelly.netlogo").joinpath("models", args.example + SUFFIX)
        return resource.read_text(encoding="utf-8"), args.example, args.example + SUFFIX
    if not args.model:
        raise ValueError("give a .nlogo file or --example NAME")
    path = Path(args.model)
    return path.read_text(encoding="utf-8"), path.stem, str(path)


def report(translation: Translation, label: str) -> str:
    """One line per dropped NetLogo line: where, why, and the source."""
    lines = []
    for issue in translation.issues:
        why = (
            "display only, dropped"
            if issue.display_only
            else f"not translated: {issue.reason}"
        )
        lines.append(f"{label}:{issue.line}: {why}: {issue.text}\n")
    return "".join(lines)


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Translate the model and return the exit status; ``prog`` names the command."""
    args = build_parser(prog).parse_args(argv)
    try:
        text, stem, label = read_source(args)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"modelly netlogo: {error}\n")
        return EXIT_USAGE
    if args.show:
        sys.stdout.write(text)
        return EXIT_CLEAN
    translation = translate(text, args.name or stem)
    if args.output:
        Path(args.output).write_text(translation.source, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(translation.source)
    sys.stderr.write(report(translation, label))
    return EXIT_UNTRANSLATED if translation.untranslated else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
