#!/usr/bin/env python3
"""Turn a coverage.xml report into the README coverage badge.

    python3 scripts/coverage_badge.py coverage.xml docs/images/badges/coverage.svg

scripts/ci-local.sh runs this after its test stage, so the committed badge is
refreshed by the same local gate that produces the number. No third-party
service, no token, no network.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# (minimum percent, badge colour), checked from the top down; shields.io palette.
COLOUR_STEPS = (
    (90.0, "#4C1"),
    (80.0, "#97CA00"),
    (70.0, "#DFB317"),
    (60.0, "#FE7D37"),
)
FALLBACK_COLOUR = "#E05D44"
PERCENT = 100.0

LABEL = "coverage"
LABEL_WIDTH = 61  # px, "coverage" in 11px Verdana plus padding
CHAR_WIDTH = 7  # px per character of the value, Verdana 11px digits
VALUE_PADDING = 12  # px around the value text

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#BBB" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
  <clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#FFF"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{lw}" height="20" fill="#555"/>
    <rect x="{lw}" width="{vw}" height="20" fill="{colour}"/>
    <rect width="{w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#FFF" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{lx}" y="15" fill="#010101" fill-opacity=".3">{label}</text><text x="{lx}" y="14">{label}</text>
    <text x="{vx}" y="15" fill="#010101" fill-opacity=".3">{value}</text><text x="{vx}" y="14">{value}</text>
  </g>
</svg>
"""


def line_rate(report: Path) -> float:
    """Total line coverage in percent, as recorded by coverage.py."""
    root = ET.parse(report).getroot()  # noqa: S314 - our own test artefact
    return float(root.attrib["line-rate"]) * PERCENT


def colour_for(percent: float) -> str:
    """Badge colour for a coverage percentage."""
    return next((c for floor, c in COLOUR_STEPS if percent >= floor), FALLBACK_COLOUR)


def badge(percent: float) -> str:
    """Flat two-part SVG badge, self-contained so GitHub renders it from the repo."""
    value = f"{percent:.0f}%"
    vw = len(value) * CHAR_WIDTH + VALUE_PADDING
    return SVG.format(
        w=LABEL_WIDTH + vw,
        lw=LABEL_WIDTH,
        vw=vw,
        lx=LABEL_WIDTH / 2,
        vx=LABEL_WIDTH + vw / 2,
        label=LABEL,
        value=value,
        colour=colour_for(percent),
    )


def main(argv: list[str]) -> int:
    """Write the badge for ``argv = [report, out]``."""
    if len(argv) != 2:
        sys.stderr.write(__doc__ or "")
        return 2
    report, out = Path(argv[0]), Path(argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(badge(line_rate(report)), encoding="utf-8")
    print(f"{out}  {line_rate(report):.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
