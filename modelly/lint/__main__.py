"""Command line for ``python -m modelly.lint``; exits 1 when there are findings, 2 on bad input."""

from __future__ import annotations

import argparse
import dataclasses
import sys

from modelly.lint import GUIDE, lint_paths
from modelly.lint.config import Config, load_config, prefixes
from modelly.lint.explain import explain
from modelly.lint.fix import FixReport, fix_paths
from modelly.lint.report import FORMATS, list_rules, render, statistics

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
PROG = "python -m modelly.lint"

DESCRIPTION = """\
Find reproducibility bugs and O(N^2) patterns in Modelly models.

The files are parsed, never imported or run, so the check is fast and safe on any
code. Each finding is printed as `path:line:col: CODE message` with a hint."""

EPILOG = f"""\
examples:
  python -m modelly.lint                          every .py file under the current folder
  python -m modelly.lint model.py agents.py       just these files
  python -m modelly.lint --select MDL0 src/       errors only (reproducibility)
  python -m modelly.lint --ignore MDL105,MDL107 src/
  python -m modelly.lint --statistics src/        how many findings of each rule
  python -m modelly.lint --format github src/     annotations in a GitHub Actions log
  python -m modelly.lint --diff src/              the safe fixes, as a diff; nothing written
  python -m modelly.lint --fix src/               apply them, then report what is left
  python -m modelly.lint --explain MDL101         why a rule matters, a bad and a good example
  python -m modelly.lint --list-rules             every rule, one line each

rule codes:
  MDL0xx  errors: the result is wrong or does not reproduce from the seed
  MDL1xx  warnings: the result is right but its cost grows faster than needed

suppressing a finding (on the line the finding points at):
  x = random.random()  # noqa: MDL001         skip one rule (several: MDL001, MDL101)
  x = random.random()  # noqa                 skip every rule on the line

configuration, in the nearest pyproject.toml from the working directory up:
  [tool.modelly.lint]
  select = ["MDL0", "MDL101"]
  ignore = ["MDL105"]
  per-file-ignores = {{ "tests/*" = ["MDL001"] }}
  --select and --ignore on the command line replace the file's values.

exit status:
  {EXIT_CLEAN}  no findings (or --exit-zero)
  {EXIT_FINDINGS}  at least one finding (with --diff: at least one fix to apply)
  {EXIT_USAGE}  usage error: unreadable path, syntax error, bad configuration, unknown rule

rules, examples and fixes: {GUIDE}"""  # noqa: S608 (help text, not SQL)


def build_parser(prog: str = PROG) -> argparse.ArgumentParser:
    """The argument parser, with the examples and exit codes in its help."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths", nargs="*", default=["."], help="files or directories (default: .)"
    )
    parser.add_argument(
        "--select",
        metavar="CODES",
        help="only these comma-separated codes or prefixes, e.g. MDL0,MDL101",
    )
    parser.add_argument(
        "--ignore", metavar="CODES", help="skip these codes or prefixes"
    )
    parser.add_argument(
        "--format",
        choices=FORMATS,
        default="text",
        help="output format (default: text)",
    )
    add_modes(parser)
    return parser


def add_fixes(parser: argparse.ArgumentParser) -> None:
    """The options that rewrite the files, or show how they would be rewritten."""
    parser.add_argument(
        "--fix",
        action="store_true",
        help="apply the safe fixes (MDL001-003, MDL009, MDL011), then report the rest",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="print the safe fixes as a unified diff without writing them",
    )


def add_modes(parser: argparse.ArgumentParser) -> None:
    """The options that change what is printed rather than what is checked."""
    add_fixes(parser)
    parser.add_argument(
        "--statistics",
        action="store_true",
        help="print a count per rule instead of each finding",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only the location lines: no hints, no summary",
    )
    parser.add_argument(
        "--exit-zero", action="store_true", help="exit 0 even with findings"
    )
    parser.add_argument(
        "--explain", metavar="CODE", help="explain one rule in detail and exit"
    )
    parser.add_argument(
        "--list-rules", action="store_true", help="print the rules and exit"
    )


def settings(args: argparse.Namespace) -> Config:
    """The pyproject.toml configuration, with --select and --ignore taking precedence."""
    config = load_config()
    if args.select is not None:
        config = dataclasses.replace(config, select=prefixes(args.select))
    if args.ignore is not None:
        config = dataclasses.replace(config, ignore=prefixes(args.ignore))
    return config


def print_explanation(code: str) -> int:
    """Print the long form of ``code``; a usage error when it is not a rule."""
    try:
        sys.stdout.write(explain(code) + "\n")
    except KeyError:
        sys.stderr.write(f"modelly.lint: unknown rule {code!r} (see --list-rules)\n")
        return EXIT_USAGE
    return EXIT_CLEAN


def run_fixes(args: argparse.Namespace, config: Config) -> FixReport:
    """Apply (--fix) or print (--diff) the safe fixes; nothing when neither is given."""
    if not (args.fix or args.diff):
        return FixReport()
    report = fix_paths(args.paths, config.keeps, write=not args.diff)
    if args.diff:
        sys.stdout.write("".join(report.diffs))
    return report


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run the checks and return the exit status; ``prog`` names the command in --help."""
    args = build_parser(prog).parse_args(argv)
    if args.list_rules:
        sys.stdout.write(list_rules() + "\n")
        return EXIT_CLEAN
    if args.explain:
        return print_explanation(args.explain)
    try:
        config = settings(args)
        report = run_fixes(args, config)
        if args.diff:
            return EXIT_FINDINGS if report.edits else EXIT_CLEAN
        findings = [f for f in lint_paths(args.paths) if config.keeps(f)]
    except (OSError, SyntaxError, ValueError) as error:
        sys.stderr.write(f"modelly.lint: {error}\n")
        return EXIT_USAGE
    if args.statistics:
        output = statistics(findings, args.quiet)
    else:
        output = render(findings, args.format, args.quiet)
    if output:
        sys.stdout.write(output + "\n")
    if args.fix:
        sys.stderr.write(f"modelly.lint: {report.edits} fix(es) applied\n")
    return EXIT_FINDINGS if findings and not args.exit_zero else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
