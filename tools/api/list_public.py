#!/usr/bin/env python3
"""List every public name of modelly with its stability level.

    python tools/api/list_public.py              name and level, one per line
    python tools/api/list_public.py --missing    names with no entry; exit 1 if any
    python tools/api/list_public.py --add-new    record missing names as provisional

A public module is one whose dotted path has no part starting with ``_`` (the bundled
examples are documentation, not API). Its public names are its ``__all__`` or, without
one, the classes and functions it defines whose names do not start with ``_``. Each
name is ``module.name``; its level (stable or provisional) is read from
``docs/api_stability.toml``. Names new in a minor release are provisional; see
``docs/deprecations.md`` for what each level promises.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STABILITY = ROOT / "docs" / "api_stability.toml"
PACKAGE = "modelly"
EXCLUDED = ("modelly.examples",)
LEVELS = ("stable", "provisional")
NEW_LEVEL = "provisional"
EXIT_OK, EXIT_MISSING = 0, 1


def _public(name: str) -> bool:
    if any(part.startswith("_") for part in name.split(".")):
        return False
    return not any(name == e or name.startswith(e + ".") for e in EXCLUDED)


def public_modules(package: str = PACKAGE) -> list[str]:
    """Dotted names of the public modules of ``package``, sorted."""
    root = importlib.import_module(package)
    found = [package]
    for info in pkgutil.walk_packages(root.__path__, prefix=package + "."):
        if _public(info.name):
            found.append(info.name)
    return sorted(found)


def module_names(module) -> list[str]:
    """The public names of ``module``: ``__all__``, else what it defines."""
    if hasattr(module, "__all__"):
        return sorted(str(name) for name in module.__all__)
    return sorted(
        name
        for name, value in vars(module).items()
        if not name.startswith("_")
        and (inspect.isclass(value) or inspect.isfunction(value))
        and getattr(value, "__module__", None) == module.__name__
    )


def public_names(package: str = PACKAGE) -> tuple[list[str], list[str]]:
    """Every public ``module.name``, and the modules that could not be imported."""
    names, failed = [], []
    for module_name in public_modules(package):
        try:
            module = importlib.import_module(module_name)
        except ImportError:  # an optional dependency is missing
            failed.append(module_name)
            continue
        names += [f"{module_name}.{name}" for name in module_names(module)]
    return sorted(set(names)), failed


def read_levels(path: Path = STABILITY) -> dict[str, str]:
    """``{name: level}`` from the stability file."""
    with path.open("rb") as handle:
        table = tomllib.load(handle)
    return {
        name: level
        for level in LEVELS
        for name in table.get(level, {}).get("names", [])
    }


def write_levels(levels: dict[str, str], path: Path = STABILITY) -> None:
    """Write ``{name: level}`` to the stability file, one sorted list per level."""
    lines = [
        "# Stability level of every public name: python tools/api/list_public.py",
        "# stable: follows docs/deprecations.md. provisional: new in a minor release,",
        "# may change in the next one with a changelog entry.",
    ]
    for level in LEVELS:
        lines += ["", f"[{level}]", "names = ["]
        lines += [
            f'  "{name}",'
            for name in sorted(n for n, lv in levels.items() if lv == level)
        ]
        lines.append("]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    """Print the names, the missing ones, or record the missing ones as provisional."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--missing", action="store_true", help="names with no entry")
    action.add_argument(
        "--add-new", action="store_true", help="record them as provisional"
    )
    args = parser.parse_args(argv)
    names, failed = public_names()
    for module_name in failed:
        sys.stderr.write(f"skipped {module_name}: an optional dependency is missing\n")
    levels = read_levels()
    missing = [name for name in names if name not in levels]
    if args.add_new:
        write_levels(levels | dict.fromkeys(missing, NEW_LEVEL))
        sys.stdout.write(f"recorded {len(missing)} new names as {NEW_LEVEL}\n")
        return EXIT_OK
    shown = missing if args.missing else names
    sys.stdout.writelines(f"{name}\t{levels.get(name, 'MISSING')}\n" for name in shown)
    return EXIT_MISSING if args.missing and missing else EXIT_OK


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))  # list the checkout this script belongs to
    sys.exit(main())
