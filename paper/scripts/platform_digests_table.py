"""The table of the golden examples' digests across hosted builds: tables/platform_digests.tex.

    python paper/scripts/platform_digests_table.py

Reads the exact digests the platform-digests workflow uploaded for each build in three runs
(data/platform_digests/: the checkout built on nine builds, three systems by three
interpreters; data/platform_digests_15/: the checkout on fifteen, five runner
architectures by three interpreters; data/platform_digests_wheels/: the released 1.4.2
wheels from PyPI on the same fifteen) and the golden file, and writes one line per example:
how the golden suite compares it (exact or ten significant digits), how many distinct
exact digests each run gave, and which wheel builds agree.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
RUNS = {
    "9": PAPER / "data" / "platform_digests",
    "15": PAPER / "data" / "platform_digests_15",
    "wheels": PAPER / "data" / "platform_digests_wheels",
}
GOLDEN = ROOT / "tests" / "determinism" / "golden.json"
RUNNER = {
    "ubuntu": "Linux x86",
    "ubuntu-latest": "Linux x86",
    "ubuntu-24.04-arm": "Linux ARM",
    "macos": "macOS ARM",
    "macos-latest": "macOS ARM",
    "macos-15-intel": "macOS x86",
    "windows": "Windows",
    "windows-latest": "Windows",
}


def digests(folder: Path) -> dict[str, dict[str, str]]:
    """Build name -> example -> exact digest."""
    return {
        f.stem.removeprefix("digests-"): json.loads(f.read_text())
        for f in sorted(folder.glob("digests-*.json"))
    }


def split(build: str) -> tuple[str, str]:
    """``ubuntu-24.04-arm-3.12`` -> (runner label, version)."""
    runner, version = build.rsplit("-", 1)
    return RUNNER[runner], version


def groups(values: dict[str, str]) -> str:
    """The builds that share a digest, as ``Linux x86-64, Windows (6); macOS ARM64 (3)``."""
    by_digest: dict[str, list[str]] = collections.defaultdict(list)
    for build, digest in sorted(values.items()):
        by_digest[digest].append(build)
    parts = []
    for builds in sorted(by_digest.values(), key=len, reverse=True):
        per_runner: dict[str, list[str]] = collections.defaultdict(list)
        for b in builds:
            runner, version = split(b)
            per_runner[runner].append(version)
        label = ", ".join(
            runner if len(versions) == 3 else f"{runner} {'/'.join(sorted(versions))}"
            for runner, versions in sorted(per_runner.items())
        )
        parts.append(f"{label} ({len(builds)})")
    return "; ".join(parts)


def main() -> None:
    """Write the table."""
    data = {run: digests(folder) for run, folder in RUNS.items()}
    golden = json.loads(GOLDEN.read_text())["examples"]
    lines = [
        "\\begin{tabularx}{\\linewidth}{llrrr>{\\raggedright\\arraybackslash}X}",
        "\\toprule",
        " & & \\multicolumn{3}{c}{distinct digests} & \\\\",
        "\\cmidrule(lr){3-5}",
        (
            "Example & Golden comparison & 9 & 15 & wheels & "
            "Wheel builds that agree (x86: x86-64; ARM: ARM64) \\\\"
        ),
        "\\midrule",
    ]
    identical = dict.fromkeys(RUNS, 0)
    for name in sorted(golden):
        counts = {}
        for run, builds in data.items():
            values = {b: d[name] for b, d in builds.items() if name in d}
            counts[run] = len(set(values.values()))
            identical[run] += counts[run] == 1
        wheels = {b: d[name] for b, d in data["wheels"].items() if name in d}
        digits = golden[name]["float_digits"]
        how = "exact" if digits is None else f"{digits} digits"
        if name == "commuting_city":
            how += ", Linux x86 only"
        agree = "all" if counts["wheels"] == 1 else groups(wheels)
        lines.append(
            f"\\code{{{name.replace('_', '\\_')}}} & {how} & {counts['9']} & {counts['15']} & "
            f"{counts['wheels']} & {agree} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabularx}"]
    note = ", ".join(
        f"{identical[run]} of {len(golden)} identical on the {run} run" for run in RUNS
    )
    (PAPER / "tables" / "platform_digests.tex").write_text(
        "\n".join(lines) + f"\n% {note}\n", encoding="utf-8"
    )
    print(note)


if __name__ == "__main__":
    main()
