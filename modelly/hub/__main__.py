"""``modelly hub``: find, install, publish and check models on the Modelly hub.

modelly hub search malaria             models matching every word, best first
modelly hub info age_seir              one model: summary, card, how to cite and install it
modelly hub install age_seir my_seir/  a zoo model into a folder; a package into this env
modelly hub publish .                  hub-entry.json for this project (dry run by default)
modelly hub publish . --zenodo --sign you@example.org --no-dry-run
                                       archive on Zenodo (sandbox unless --production), sign
modelly hub check index.json           the checks an index change must pass
modelly hub zoo-index > index.json     the index of the zoo models
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from modelly.hub.check import check_index
from modelly.hub.index import HubError, load, search
from modelly.hub.install import install
from modelly.hub.publish import Signer, publish, zoo_index
from modelly.hub.zenodo import TOKEN_ENVIRONMENT, DryRun, Zenodo

PROG = "python -m modelly.hub"
EXIT_OK, EXIT_PROBLEMS, EXIT_USAGE = 0, 1, 2


def _say(text: object) -> None:
    """One line on stdout."""
    sys.stdout.write(f"{text}\n")


def build_parser(prog: str) -> argparse.ArgumentParser:
    """The parser of every sub-command."""
    parser = argparse.ArgumentParser(
        prog=prog, description="The Modelly hub: published models, installed by name.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1] + "\nguide: docs/hub.md",
    )  # fmt: skip
    commands = parser.add_subparsers(dest="command", required=True)
    find = commands.add_parser("search", help="search the hub")
    find.add_argument("words", nargs="*")
    find.add_argument("--field")
    commands.add_parser("info", help="describe one model").add_argument("name")
    get = commands.add_parser("install", help="install a model")
    get.add_argument("name")
    get.add_argument("folder", nargs="?", type=Path, help="for a zoo model")
    put = commands.add_parser("publish", help="write the hub entry of a project")
    put.add_argument("folder", type=Path)
    put.add_argument(
        "--zenodo",
        action="store_true",
        help=f"archive on Zenodo (${TOKEN_ENVIRONMENT})",
    )
    put.add_argument(
        "--production", action="store_true", help="zenodo.org, not the sandbox"
    )
    put.add_argument(
        "--sign", metavar="IDENTITY", help="sign with Sigstore as IDENTITY"
    )
    put.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    commands.add_parser("check", help="check an index").add_argument("index", type=Path)
    commands.add_parser("zoo-index", help="print the zoo models' index")
    return parser


def _search(args: argparse.Namespace) -> int:
    """One line per match."""
    found = search(load(), " ".join(args.words), args.field)
    for entry in found:
        _say(f"{entry.name:<22}{entry.field:<18}{entry.summary}")
    if not found:
        _say("no model matches")
    return EXIT_OK


def _info(args: argparse.Namespace) -> int:
    """Title, summary, card summary, citation and install command."""
    entry = load().get(args.name)
    _say(
        f"{entry.title} ({entry.field}, {entry.kind} {entry.version})\n\n{entry.summary}\n"
    )
    for key in ("intended_use", "out_of_scope"):
        _say(f"{key.replace('_', ' ')}:")
        for line in entry.card.get(key, ()):
            _say(f"  - {line}")
    _say(f"\nsupports Modelly {entry.modelly}; DOI {entry.doi or 'none yet'}")
    _say(f"install: modelly hub install {entry.name}")
    return EXIT_OK


def _publish(args: argparse.Namespace) -> int:
    """Write the entry; report what was or would be sent."""
    transport = DryRun() if args.dry_run else None
    zenodo = None
    if args.zenodo:
        token = os.environ.get(TOKEN_ENVIRONMENT) or (
            "dry-run" if args.dry_run else None
        )
        if token is None:
            _say(f"set {TOKEN_ENVIRONMENT} to archive on Zenodo")
            return EXIT_USAGE
        zenodo = Zenodo(token, sandbox=not args.production, **({"transport": transport} if transport else {}))  # fmt: skip
    signer = Signer(args.sign) if args.sign else None
    done = publish(args.folder, zenodo, signer, dry_run=args.dry_run)
    for command in done.commands:
        _say(("would run: " if args.dry_run else "ran: ") + " ".join(command))
    for method, url, size in getattr(transport, "requests", []):
        _say(f"would send: {method} {url} ({size} bytes)")
    _say(f"wrote {done.path}: open a pull request adding it to the hub index")
    return EXIT_OK


def _check(args: argparse.Namespace) -> int:
    """Every problem; non-zero if there is one."""
    report = check_index(args.index)
    for name, found in report.items():
        for line in found:
            _say(f"{name or 'index'}: {line}")
    _say("index ok" if not report else f"{len(report)} entr(y/ies) with problems")
    return EXIT_PROBLEMS if report else EXIT_OK


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run ``modelly hub`` and return the exit status."""
    args = build_parser(prog).parse_args(argv)
    commands = {"search": _search, "info": _info, "publish": _publish, "check": _check}
    try:
        if args.command == "install":
            done = install(load().get(args.name), args.folder)
            _say(
                "\n".join(f"wrote {p}" for p in done.files) or f"installed {args.name}"
            )
            return EXIT_OK
        if args.command == "zoo-index":
            sys.stdout.write(json.dumps(zoo_index(), indent=2) + "\n")
            return EXIT_OK
        return commands[args.command](args)
    except (HubError, KeyError, FileExistsError) as problem:
        sys.stderr.write(f"{problem}\n")
        return EXIT_PROBLEMS


if __name__ == "__main__":
    sys.exit(main())
