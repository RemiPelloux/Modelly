"""Command line for ``python -m modelly.lint``; exits 1 when there are findings, 2 on bad input."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from modelly.lint import GUIDE, RULES, Finding, lint_paths


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(
        prog="python -m modelly.lint",
        description="Find reproducibility bugs and O(N^2) patterns in Modelly models.",
        epilog=f"Rules and examples: {GUIDE}",
    )
    parser.add_argument(
        "paths", nargs="*", default=["."], help="files or directories (default: .)"
    )
    parser.add_argument(
        "--select", default="", help="only these codes or prefixes, e.g. MDL0,MDL101"
    )
    parser.add_argument("--ignore", default="", help="skip these codes or prefixes")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--list-rules", action="store_true", help="print the rules and exit"
    )
    parser.add_argument(
        "--exit-zero", action="store_true", help="exit 0 even with findings"
    )
    return parser.parse_args(argv)


def matches(code: str, prefixes: str) -> bool:
    """Whether ``code`` starts with one of the comma-separated ``prefixes``."""
    return any(
        code.startswith(p.strip().upper()) for p in prefixes.split(",") if p.strip()
    )


def keep(finding: Finding, args: argparse.Namespace) -> bool:
    """Apply --select and --ignore."""
    code = finding.rule.code
    if args.select and not matches(code, args.select):
        return False
    return not (args.ignore and matches(code, args.ignore))


def report(findings: list[Finding], output: str) -> str:
    """Render ``findings`` as text with a summary line, or as a JSON list."""
    if output == "json":
        return json.dumps([asdict(f) for f in findings], indent=2)
    errors = sum(f.rule.severity == "error" for f in findings)
    lines = [str(f) for f in findings]
    lines.append(
        f"{len(findings)} finding(s): {errors} error(s), {len(findings) - errors} warning(s)"
    )
    return "\n".join(lines)


def list_rules() -> str:
    """One line per rule."""
    return "\n".join(f"{r.code}  {r.severity:<7}  {r.message}" for r in RULES.values())


def main(argv: list[str] | None = None) -> int:
    """Run the checks and return the exit status."""
    args = parse_args(argv)
    if args.list_rules:
        sys.stdout.write(list_rules() + "\n")
        return 0
    try:
        findings = [f for f in lint_paths(args.paths) if keep(f, args)]
    except (OSError, SyntaxError) as error:
        sys.stderr.write(f"modelly.lint: {error}\n")
        return 2
    sys.stdout.write(report(findings, args.format) + "\n")
    return 1 if findings and not args.exit_zero else 0


if __name__ == "__main__":
    sys.exit(main())
