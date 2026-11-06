"""The golden examples' exact digests across the local builds: data/local_digests/summary.json.

    python paper/scripts/local_digests.py

Reads the exact (unrounded) digests that ``python -m modelly.dev golden --json`` wrote on the
development machine for each local build (data/local_digests/digests-<platform>-<python>-
<compiled|pure>.json, made by paper/measure/measure_150b.sh), checks every build covers every
golden example, and writes, per example, how the golden suite compares it (exact or at ten
significant digits) and how many distinct exact digests the builds gave. Exits non-zero if an
example is missing from a build or two builds disagree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
FOLDER = PAPER / "data" / "local_digests"
sys.path.insert(0, str(PAPER.parent))

from modelly.dev.golden import EXAMPLES  # noqa: E402


def builds() -> dict[str, dict[str, str]]:
    """Build name (``linux-x86_64-3.12-pure``) -> example -> exact digest."""
    return {
        f.stem.removeprefix("digests-"): json.loads(f.read_text())
        for f in sorted(FOLDER.glob("digests-*.json"))
    }


def summary(found: dict[str, dict[str, str]]) -> dict:
    """Per example: comparison mode and distinct digests; and the builds compared."""
    examples = {}
    for example in EXAMPLES:
        values = {build: d.get(example.name) for build, d in found.items()}
        examples[example.name] = {
            "golden_comparison": "exact"
            if example.float_digits is None
            else f"{example.float_digits} significant digits",
            "missing_from": sorted(b for b, v in values.items() if v is None),
            "distinct_digests": len({v for v in values.values() if v is not None}),
        }
    return {"builds": sorted(found), "examples": examples}


def main() -> int:
    """Write the summary; exit 1 if an example is missing or the builds disagree."""
    result = summary(builds())
    (FOLDER / "summary.json").write_text(json.dumps(result, indent=1) + "\n")
    bad = {
        n: e
        for n, e in result["examples"].items()
        if e["missing_from"] or e["distinct_digests"] != 1
    }
    print(
        f"{len(result['builds'])} builds, {len(result['examples'])} examples, "
        f"{len(result['examples']) - len(bad)} with one digest on every build"
    )
    for name, entry in bad.items():
        print(f"  {name}: {entry}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
