"""Turn the newest version's folder of the docs site into redirects to the root.

    python scripts/docs_redirects.py <site> <X.Y>

The root of the site holds the newest minor release, and its pages are the canonical
ones; ``<site>/<X.Y>`` would be a second full copy. This replaces each of its HTML pages
by a small page that sends the reader to the same page at the root (keeping the
``#anchor``), and drops the assets only those pages used. Text files (the ``.md`` copy of
each page, ``llms.txt``, ``objects.inv``) stay, so their addresses keep working.

A marker file records that the folder is made of redirects: before a newer minor
replaces the root, ``scripts/assemble-docs-site.sh`` fills the folder again from the root.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

MARKER = ".redirects-to-root"
ASSET_DIRS = ("_static", "_images", "_sources", "_downloads")
ASSET_FILES = ("searchindex.js", ".buildinfo")
PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Modelly</title>
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace({target!r} + location.search + location.hash)</script>
<p>This page is at <a href="{target}">{target}</a>.</p>
"""


def redirect_page(page: Path, folder: Path) -> None:
    """Replace one HTML page by a redirect to the same path one level up."""
    relative = page.relative_to(folder).as_posix()
    depth = relative.count("/") + 1
    target = "../" * depth + relative
    page.write_text(PAGE.format(target=target), encoding="utf-8")


def drop_assets(folder: Path) -> None:
    """Remove what only the full pages needed: theme files, images, search index."""
    for name in ASSET_DIRS:
        shutil.rmtree(folder / name, ignore_errors=True)
    for name in ASSET_FILES:
        (folder / name).unlink(missing_ok=True)


def to_redirects(folder: Path) -> int:
    """Make ``folder`` a set of redirects to the root; return how many pages."""
    drop_assets(folder)
    pages = sorted(folder.rglob("*.html"))
    for page in pages:
        redirect_page(page, folder)
    for path in sorted(folder.rglob("*"), reverse=True):  # emptied asset folders
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    (folder / MARKER).write_text(
        "pages here redirect to the site root\n", encoding="utf-8"
    )
    return len(pages)


def main(argv: list[str]) -> int:
    """Command line: ``docs_redirects.py <site> <X.Y>``."""
    if len(argv) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    folder = Path(argv[0]) / argv[1]
    if not folder.is_dir():
        print(f"no folder {folder}", file=sys.stderr)
        return 2
    count = to_redirects(folder)
    print(f"{folder.name}: {count} pages now redirect to the site root")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
