"""``modelly plugins``: the installed plugins, the Modelly they support, and whether they load.

modelly plugins           every group, each plugin with its distribution and declaration
modelly plugins --check   also import each one; exit 1 if any is incompatible or fails
"""

from __future__ import annotations

import argparse
import sys

import modelly
from modelly.plugins import API_VERSION, GROUPS, Plugin, PluginError, discover

PROG = "python -m modelly._plugins_cli"
EXIT_OK, EXIT_FAILED = 0, 1


def status(plugin: Plugin, check: bool) -> str:
    """``ok``, ``incompatible``, ``undeclared`` or the load error."""
    if not plugin.compatible:
        return "incompatible"
    if check:
        try:
            plugin.load()
        except PluginError as error:
            return f"fails to load: {error.__cause__ or error}"
    return "ok" if plugin.requires is not None else "ok (declares no Modelly version)"


def report(check: bool) -> tuple[list[str], bool]:
    """The report's lines, and whether every plugin is usable."""
    lines = [f"Modelly {modelly.__version__}, plugin API v{API_VERSION}"]
    usable = True
    for group in GROUPS:
        plugins = discover(group)
        lines.append(f"{group}: {len(plugins) or 'none'}")
        for name, plugin in plugins.items():
            state = status(plugin, check)
            usable &= state.startswith("ok")
            declared = f"modelly-abm{plugin.requires}" if plugin.requires else "-"
            lines.append(
                f"  {name:<16}{plugin.distribution or '?':<28}{declared:<24}{state}"
            )
    return lines, usable


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Print the report; with ``--check``, non-zero when a plugin is not usable."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description="List the installed Modelly plugins.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1] + "\nguide: docs/plugins.md",
    )
    parser.add_argument("--check", action="store_true", help="import every plugin")
    args = parser.parse_args(argv)
    lines, usable = report(args.check)
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK if usable or not args.check else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
