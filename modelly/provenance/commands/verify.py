"""``modelly verify``: rerun a manifest and compare the outputs with the recorded ones."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from modelly.profile.loader import TargetError
from modelly.provenance.commands.common import (
    EXIT_FAILED,
    EXIT_MODEL_ERROR,
    EXIT_OK,
    EXIT_USAGE,
    GUIDE,
    add_options,
    error,
    make_parser,
    non_negative,
)
from modelly.provenance.compare import Tolerance
from modelly.provenance.manifest import ManifestError
from modelly.provenance.verify import verify

PROG = "python -m modelly.provenance.commands.verify"

DESCRIPTION = """\
Rerun the run a manifest records (same model, parameters, seed and steps), then
compare every output table with the recorded one, column by column and row by
row. Prints "outputs match", or the first difference: its table, column, row
(0-based position) and both values.

Numeric columns match when numpy.isclose(new, recorded, rtol, atol) holds;
both tolerances are 0 by default, so values must be identical. Other columns
must be equal. Before the rerun, model source files, input files and the
Modelly and Python versions are checked against the record; what differs is
printed as a note on stderr and does not by itself fail the check.

The manifest may be inside a run folder written by `modelly run` or an
unpacked `modelly bundle` archive; its paths are relative to its own folder.
"""

EPILOG = f"""\
examples:
  modelly verify runs/manifest.json
  modelly verify runs/                          the manifest in a run folder
  modelly verify study/manifest.json --rtol 1e-12
  modelly verify runs/manifest.json --atol 1e-9 --rtol 0

exit codes:
  0  outputs match
  1  an output differs (the first difference is printed)
  2  bad command line, unreadable or unsupported manifest, or the model cannot
     be loaded
  3  the model raised during the rerun (traceback on stderr)

guide: {GUIDE}
"""

OPTIONS = (
    (("manifest",), {"type": Path, "help": "manifest.json, or the folder holding it"}),
    (
        ("--rtol",),
        {
            "type": non_negative,
            "default": 0.0,
            "help": "relative tolerance for numeric columns (default: %(default)s)",
        },
    ),
    (
        ("--atol",),
        {
            "type": non_negative,
            "default": 0.0,
            "help": "absolute tolerance for numeric columns (default: %(default)s)",
        },
    ),
)


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Rerun and compare; the exit status."""
    parser = make_parser(prog, DESCRIPTION, EPILOG)
    add_options(parser, OPTIONS)
    args = parser.parse_args(argv)
    try:
        result = verify(args.manifest, Tolerance(rtol=args.rtol, atol=args.atol))
    except (ManifestError, TargetError) as problem:
        error(prog, problem)
        return EXIT_USAGE
    except Exception:  # any model error is reported, not raised
        traceback.print_exc()
        return EXIT_MODEL_ERROR
    for note in result.notes:
        error(prog, f"note: {note}")
    if result.matches:
        sys.stdout.write("outputs match\n")
        return EXIT_OK
    sys.stdout.write(f"outputs differ: {result.difference}\n")
    return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
