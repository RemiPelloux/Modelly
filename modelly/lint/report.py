"""Rendering findings: text for people, JSON for tools, annotations for GitHub Actions."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict

from modelly.lint import RULES, Finding

FORMATS = ("text", "json", "github")
# GitHub workflow commands: characters that must be escaped in the message and in properties.
DATA_ESCAPES = (("%", "%25"), ("\r", "%0D"), ("\n", "%0A"))
PROPERTY_ESCAPES = (*DATA_ESCAPES, (":", "%3A"), (",", "%2C"))


def summary(findings: list[Finding]) -> str:
    """``N finding(s): E error(s), W warning(s)``."""
    errors = sum(f.rule.severity == "error" for f in findings)
    return f"{len(findings)} finding(s): {errors} error(s), {len(findings) - errors} warning(s)"


def text(findings: list[Finding], quiet: bool = False) -> str:
    """One ``path:line:col: CODE message`` per finding; hints and a summary unless ``quiet``."""
    if quiet:
        return "\n".join(f.location() for f in findings)
    return "\n".join([*(str(f) for f in findings), summary(findings)])


def escape(value: str, table: tuple[tuple[str, str], ...]) -> str:
    """Escape ``value`` for a GitHub workflow command."""
    for char, code in table:
        value = value.replace(char, code)
    return value


def github(findings: list[Finding]) -> str:
    """``::error file=...,line=...,col=...,title=CODE::message`` per finding."""
    lines = []
    for f in findings:
        props = f"file={escape(f.path, PROPERTY_ESCAPES)},line={f.line},col={f.column}"
        message = escape(f"{f.rule.message}. Hint: {f.rule.hint}", DATA_ESCAPES)
        lines.append(f"::{f.rule.severity} {props},title={f.rule.code}::{message}")
    return "\n".join(lines)


def statistics(findings: list[Finding], quiet: bool = False) -> str:
    """How many findings of each code, most frequent first."""
    counts = Counter(f.rule.code for f in findings)
    width = len(str(max(counts.values(), default=0)))
    lines = [
        f"{count:>{width}}  {code}  {RULES[code].severity:<7}  {RULES[code].message}"
        for code, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return "\n".join(lines if quiet else [*lines, summary(findings)])


def render(findings: list[Finding], output: str, quiet: bool = False) -> str:
    """Render ``findings`` in one of ``FORMATS``."""
    if output == "json":
        return json.dumps([asdict(f) for f in findings], indent=2)
    if output == "github":
        return github(findings)
    return text(findings, quiet)


def list_rules() -> str:
    """One line per rule: code, severity, message."""
    return "\n".join(f"{r.code}  {r.severity:<7}  {r.message}" for r in RULES.values())
