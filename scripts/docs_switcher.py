"""Write switcher.json for an assembled docs site, from the version folders it holds.

    python scripts/docs_switcher.py <site>            # writes <site>/switcher.json
    python scripts/docs_switcher.py <site> --newest   # prints the newest X.Y folder

The newest X.Y folder is the stable version: its entry points at the site root, where
a copy of it lives, and is the preferred one the old-version banner links to.
"""

import json
import re
import sys
from pathlib import Path

SITE_URL = "https://remipelloux.github.io/Modelly/"
DEV_FOLDER = "dev"
MINOR_FOLDER = re.compile(r"^(\d+)\.(\d+)$")
JSON_INDENT = 2


def minor_folders(site: Path) -> list[str]:
    """Return the X.Y folders of ``site``, newest first."""
    found = [
        p.name for p in site.iterdir() if p.is_dir() and MINOR_FOLDER.match(p.name)
    ]
    return sorted(
        found, key=lambda name: tuple(map(int, name.split("."))), reverse=True
    )


def switcher_entries(site: Path) -> list[dict]:
    """Return the switcher entries: the stable version, then dev, then older minors."""
    minors = minor_folders(site)
    entries = []
    if minors:
        stable = minors[0]
        entries.append(
            {
                "name": f"{stable} (stable)",
                "version": stable,
                "url": SITE_URL,
                "preferred": True,
            }
        )
    if (site / DEV_FOLDER).is_dir():
        entries.append(
            {"name": "dev", "version": DEV_FOLDER, "url": f"{SITE_URL}{DEV_FOLDER}/"}
        )
    entries += [{"name": m, "version": m, "url": f"{SITE_URL}{m}/"} for m in minors[1:]]
    return entries


def main(argv: list[str]) -> int:
    """Write switcher.json, or print the newest minor with ``--newest``."""
    site = Path(argv[0])
    if argv[1:] == ["--newest"]:
        minors = minor_folders(site)
        sys.stdout.write(f"{minors[0] if minors else ''}\n")
        return 0
    text = json.dumps(switcher_entries(site), indent=JSON_INDENT)
    (site / "switcher.json").write_text(f"{text}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
