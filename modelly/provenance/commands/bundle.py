"""``modelly bundle``: pack a recorded run into a deterministic zip."""

from __future__ import annotations

import sys
from pathlib import Path

from modelly.provenance.bundle import BundleError, bundle
from modelly.provenance.commands.common import (
    EXIT_OK,
    EXIT_USAGE,
    GUIDE,
    add_options,
    error,
    make_parser,
)
from modelly.provenance.manifest import ManifestError

PROG = "python -m modelly.provenance.commands.bundle"

DESCRIPTION = """\
Pack the run recorded in a folder written by `modelly run` into one zip:

  manifest.json      the manifest, its paths rewritten for the archive
  <outputs>          the output tables, as recorded
  code/              the model's source files
  inputs/            the --input files and the scenario file of the run
  requirements.lock  name==version of every package installed at run time
  seeds.json         the seed, its expanded seed sequence and the step count
  .zenodo.json       Zenodo deposit metadata, with TODO markers to fill in
  CITATION.cff       a citation stub for the study, citing Modelly

Entries are sorted, stored uncompressed and carry a fixed time and mode, so the
same run gives a byte-identical archive on any machine. The outputs and code
must be unchanged since the run (their hashes are checked). A reviewer unpacks
the archive and runs `modelly verify manifest.json` inside it.
"""

EPILOG = f"""\
examples:
  modelly bundle runs/ --out epidemic-study.zip
  modelly bundle runs/manifest.json --out study.zip

exit codes:
  0  the archive was written
  2  bad command line, unreadable manifest, or outputs or code changed since
     the run (rerun `modelly run`)

guide: {GUIDE}
"""

OPTIONS = (
    (("run",), {"type": Path, "help": "the run folder, or its manifest.json"}),
    (
        ("--out",),
        {"type": Path, "required": True, "metavar": "ZIP", "help": "archive to write"},
    ),
)


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Write the bundle; the exit status."""
    parser = make_parser(prog, DESCRIPTION, EPILOG)
    add_options(parser, OPTIONS)
    args = parser.parse_args(argv)
    try:
        path = bundle(args.run, args.out)
    except (ManifestError, BundleError, OSError) as problem:
        error(prog, problem)
        return EXIT_USAGE
    sys.stdout.write(f"wrote {path.as_posix()}\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
