"""The table of the golden examples' digests across nine hosted builds: tables/platform_digests.tex.

    python paper/scripts/platform_digests_table.py

Reads the exact digests the platform-digests workflow uploaded for each (OS, CPython)
build (data/platform_digests/digests-<os>-<version>.json) and the golden file, and
writes one line per example: how the golden suite compares it (exact or ten significant
digits), how many distinct exact digests the nine builds gave, and which builds agree.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
DIGESTS = PAPER / "data" / "platform_digests"
GOLDEN = ROOT / "tests" / "determinism" / "golden.json"
OS_LABEL = {"ubuntu": "Linux", "macos": "macOS", "windows": "Windows"}


def groups(values: dict[str, str]) -> str:
    """The builds that share a digest, as ``Linux+Windows (6) / macOS (3)``."""
    by_digest: dict[str, list[str]] = collections.defaultdict(list)
    for build, digest in sorted(values.items()):
        by_digest[digest].append(build)
    parts = []
    for builds in sorted(by_digest.values(), key=len, reverse=True):
        per_os: dict[str, list[str]] = collections.defaultdict(list)
        for b in builds:
            system, version = b.split("-")
            per_os[OS_LABEL[system]].append(version)
        label = ", ".join(
            system if len(versions) == 3 else f"{system} {'/'.join(sorted(versions))}"
            for system, versions in sorted(per_os.items())
        )
        parts.append(f"{label} ({len(builds)})")
    return "; ".join(parts)


def main() -> None:
    """Write the table."""
    files = sorted(DIGESTS.glob("digests-*.json"))
    data = {f.stem.removeprefix("digests-"): json.loads(f.read_text()) for f in files}
    golden = json.loads(GOLDEN.read_text())["examples"]
    lines = [
        "\\begin{tabularx}{\\linewidth}{llr>{\\raggedright\\arraybackslash}X}",
        "\\toprule",
        "Example & Golden comparison & Distinct & Builds that agree \\\\",
        "\\midrule",
    ]
    identical = 0
    for name in sorted(golden):
        values = {b: d[name] for b, d in data.items() if name in d}
        distinct = len(set(values.values()))
        identical += distinct == 1
        digits = golden[name]["float_digits"]
        how = "exact" if digits is None else f"{digits} digits"
        if name == "commuting_city":
            how += ", Linux only"
        lines.append(
            f"\\code{{{name.replace('_', '\\_')}}} & {how} & {distinct} & "
            f"{'all nine' if distinct == 1 else groups(values)} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabularx}"]
    (PAPER / "tables" / "platform_digests.tex").write_text(
        "\n".join(lines)
        + f"\n% {identical} of {len(golden)} identical on {len(data)} builds\n",
        encoding="utf-8",
    )
    print(
        f"{identical} of {len(golden)} examples bit-identical on all {len(data)} builds"
    )


if __name__ == "__main__":
    main()
