#!/usr/bin/env python3
"""Generate Modelly's animated SVG brand assets.

Run from the repository root:

    python tools/branding/generate_assets.py

Outputs (committed, served to GitHub via <picture> in README.md):

    docs/images/branding/banner-dark.svg
    docs/images/branding/banner-light.svg
    docs/images/branding/architecture.svg
    docs/images/branding/simulation-loop.svg

Everything is hand-rolled SVG (CSS keyframes + SMIL), no external fonts,
no JavaScript, so it renders inside GitHub's <img> sandbox.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "images" / "branding"

FONT = "Inter, 'Segoe UI', 'Helvetica Neue', system-ui, -apple-system, sans-serif"
MONO = "'JetBrains Mono', 'SF Mono', ui-monospace, Menlo, monospace"
PACKAGE_INIT = Path(__file__).resolve().parents[2] / "modelly" / "__init__.py"


def version_label() -> str:
    """The ``vX.Y`` shown on the banner, read from the package so it cannot go stale."""
    match = re.search(
        r'__version__ = "(\d+)\.(\d+)', PACKAGE_INIT.read_text(encoding="utf-8")
    )
    return f"v{match[1]}.{match[2]}"


DARK = {
    "bg1": "#080B1A",
    "bg2": "#150F33",
    "glow1": "#6D4AFF",
    "glow2": "#00CFE8",
    "glow3": "#FF4FA3",
    "glow_op": "0.55",
    "dot": "#9AA3FF",
    "dot_op": "0.16",
    "text": "#FFFFFF",
    "sub": "#A8B0D4",
    "pill_bg": "#191D3D",
    "pill_stroke": "#343B67",
    "pill_text": "#C7CDF0",
    "g1": "#9B7BFF",
    "g2": "#41E0FF",
    "g3": "#FF77D9",
    "node": "#A9B6FF",
    "edge": "#7C5CFF",
    "edge_op": "0.55",
    "shadow": "#000000",
    "card": "#141936",
    "card_edge": "#2B3260",
}

LIGHT = {
    "bg1": "#FFFFFF",
    "bg2": "#F2F0FF",
    "glow1": "#B7A3FF",
    "glow2": "#7FE9F4",
    "glow3": "#FFB1DF",
    "glow_op": "0.7",
    "dot": "#1B2036",
    "dot_op": "0.07",
    "text": "#0C1022",
    "sub": "#4B5375",
    "pill_bg": "#F4F3FF",
    "pill_stroke": "#DCDDF2",
    "pill_text": "#3B4270",
    "g1": "#6C3BFF",
    "g2": "#0C97B4",
    "g3": "#D4399A",
    "node": "#5C6BFF",
    "edge": "#7C5CFF",
    "edge_op": "0.45",
    "shadow": "#6D5BFF",
    "card": "#FFFFFF",
    "card_edge": "#E2E4F5",
}


def network_nodes(seed: int = 7) -> list[tuple[float, float, float]]:
    """Deterministic jittered lattice of agent-nodes for the hero graphic."""
    rnd = random.Random(seed)
    cols, rows = 6, 4
    nodes: list[tuple[float, float, float]] = []
    for r in range(rows):
        for c in range(cols):
            x = 706 + c * 78 + rnd.uniform(-14, 14)
            y = 74 + r * 66 + rnd.uniform(-14, 14)
            rad = rnd.choice([2.2, 2.6, 3.0, 3.4, 4.4, 5.2])
            nodes.append((round(x, 1), round(y, 1), rad))
    return nodes


def banner(p: dict, theme_name: str) -> str:
    """Return the 1200x340 hero banner for one colour scheme."""
    nodes = network_nodes()
    cols, rows = 6, 4

    # edges between lattice neighbours
    edges = []
    for i in range(len(nodes)):
        r, c = divmod(i, cols)
        if c + 1 < cols:
            edges.append((i, i + 1))
        if r + 1 < rows:
            edges.append((i, i + cols))
            if (r + c) % 3 == 0 and c + 1 < cols:
                edges.append((i, i + cols + 1))

    edge_svg = []
    for k, (a, b) in enumerate(edges):
        (x1, y1, _), (x2, y2, _) = nodes[a], nodes[b]
        dash = 4 + (k % 3) * 2
        edge_svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{p["edge"]}" stroke-opacity="{p["edge_op"]}" stroke-width="1.1" '
            f'stroke-dasharray="{dash} {dash + 5}" stroke-linecap="round"/>'
        )

    node_svg = []
    for x, y, rad in nodes:
        hub = rad > 4.2
        node_svg.append(
            f'<g><circle cx="{x}" cy="{y}" r="{rad}" fill="{p["node"]}"'
            + (' opacity="0.95"' if hub else ' opacity="0.8"')
            + "/>"
            + (
                f'<circle cx="{x}" cy="{y}" r="{rad * 2.6:.1f}" fill="none" '
                f'stroke="{p["node"]}" stroke-opacity="0.14" stroke-width="1"/>'
                if hub
                else ""
            )
            + "</g>"
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 340" width="1200" height="340" role="img" aria-label="Modelly — agent-based modeling in Python">
  <title>Modelly — agent-based modeling in Python</title>
  <defs>
    <linearGradient id="bg-{theme_name}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{p["bg1"]}"/>
      <stop offset="1" stop-color="{p["bg2"]}"/>
    </linearGradient>
    <linearGradient id="word-{theme_name}" x1="0" y1="0" x2="1" y2="0.4">
      <stop offset="0" stop-color="{p["g1"]}"/>
      <stop offset="0.55" stop-color="{p["g2"]}"/>
      <stop offset="1" stop-color="{p["g3"]}"/>
    </linearGradient>
    <linearGradient id="sheen-{theme_name}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#fff" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#fff" stop-opacity="0.55"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="glow1-{theme_name}" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{p["glow1"]}" stop-opacity="{p["glow_op"]}"/>
      <stop offset="1" stop-color="{p["glow1"]}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glow2-{theme_name}" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{p["glow2"]}" stop-opacity="{p["glow_op"]}"/>
      <stop offset="1" stop-color="{p["glow2"]}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glow3-{theme_name}" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{p["glow3"]}" stop-opacity="{p["glow_op"]}"/>
      <stop offset="1" stop-color="{p["glow3"]}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="dots-{theme_name}" width="26" height="26" patternUnits="userSpaceOnUse">
      <circle cx="1.4" cy="1.4" r="1.4" fill="{p["dot"]}" fill-opacity="{p["dot_op"]}"/>
    </pattern>
    <clipPath id="wordclip-{theme_name}">
      <text x="78" y="196" font-family="{FONT}" font-size="96" font-weight="700" letter-spacing="-3">Modelly</text>
    </clipPath>
    <filter id="soft-{theme_name}" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="34"/>
    </filter>
    <clipPath id="frame-{theme_name}">
      <rect width="1200" height="340" rx="26"/>
    </clipPath>
  </defs>

  <g clip-path="url(#frame-{theme_name})">
    <rect width="1200" height="340" fill="url(#bg-{theme_name})"/>
    <rect width="1200" height="340" fill="url(#dots-{theme_name})"/>

    <g filter="url(#soft-{theme_name})">
      <ellipse cx="180" cy="60" rx="230" ry="170" fill="url(#glow1-{theme_name})"/>
      <ellipse cx="470" cy="300" rx="250" ry="180" fill="url(#glow2-{theme_name})"/>
      <ellipse cx="1010" cy="250" rx="260" ry="200" fill="url(#glow3-{theme_name})"/>
    </g>

    <g>
      {"".join(edge_svg)}
      {"".join(node_svg)}
    </g>

    <g>
      <rect x="78" y="56" width="188" height="34" rx="17" fill="{p["pill_bg"]}" stroke="{p["pill_stroke"]}" stroke-width="1"/>
      <circle cx="98" cy="73" r="3.4" fill="{p["g2"]}"/>
      <text x="112" y="78" font-family="{MONO}" font-size="14" fill="{p["pill_text"]}" letter-spacing="0.6">{version_label()} · stable</text>
    </g>

    <text x="78" y="196" font-family="{FONT}" font-size="96" font-weight="700" letter-spacing="-3" fill="url(#word-{theme_name})">Modelly</text>

    <text x="82" y="248" font-family="{FONT}" font-size="26" font-weight="400" fill="{p["sub"]}" letter-spacing="0.2">Agent-based modeling in Python</text>

    <g opacity="0.9">
      <rect x="80" y="278" width="10" height="10" rx="3" fill="{p["g1"]}"/>
      <text x="100" y="288" font-family="{MONO}" font-size="13" fill="{p["sub"]}">scenario</text>
      <rect x="182" y="278" width="10" height="10" rx="3" fill="{p["g2"]}"/>
      <text x="202" y="288" font-family="{MONO}" font-size="13" fill="{p["sub"]}">agents</text>
      <rect x="272" y="278" width="10" height="10" rx="3" fill="{p["g3"]}"/>
      <text x="292" y="288" font-family="{MONO}" font-size="13" fill="{p["sub"]}">space</text>
      <rect x="356" y="278" width="10" height="10" rx="3" fill="{p["node"]}"/>
      <text x="376" y="288" font-family="{MONO}" font-size="13" fill="{p["sub"]}">data</text>
    </g>
  </g>
  <rect x="0.6" y="0.6" width="1198.8" height="338.8" rx="26" fill="none" stroke="{p["card_edge"]}" stroke-opacity="0.7"/>
</svg>
"""


def card(
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str,
    accent: str,
    *,
    card_bg: str = "#FFFFFF",
    card_edge: str = "#E2E4F5",
    title_color: str = "#0C1022",
    sub_color: str = "#5A6183",
    mono: bool = False,
    detail: str | None = None,
) -> str:
    """Return one diagram card: accent rail, title, subtitle and optional mono detail."""
    extra = (
        f'\n    <text x="{x + 22}" y="{y + 82}" font-family="{MONO}" font-size="11.5" '
        f'fill="{accent}" fill-opacity="0.85">{detail}</text>'
        if detail
        else ""
    )
    return f"""  <g>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{card_bg}" stroke="{card_edge}" stroke-width="1.2"/>
    <rect x="{x}" y="{y}" width="4" height="{h}" rx="2" fill="{accent}"/>
    <text x="{x + 22}" y="{y + 32}" font-family="{MONO if mono else FONT}" font-size="{14 if mono else 17}" font-weight="600" fill="{title_color}">{title}</text>
    <text x="{x + 22}" y="{y + 56}" font-family="{MONO}" font-size="12.5" fill="{sub_color}">{subtitle}</text>{extra}
  </g>
"""


def flow(
    a: tuple[float, float],
    b: tuple[float, float],
    accent: str,
    dur: float,
    delay: float = 0,
    curve: float = 0.0,
) -> str:
    """Dashed connector ending in a dot at its destination."""
    x1, y1 = a
    x2, y2 = b
    mx = (x1 + x2) / 2 + curve
    my = (y1 + y2) / 2
    return f"""  <g>
    <path d="M{x1} {y1} Q{mx} {my} {x2} {y2}" fill="none" stroke="{accent}" stroke-opacity="0.55" stroke-width="1.8" stroke-dasharray="5 7" stroke-linecap="round"/>
    <circle cx="{x2}" cy="{y2}" r="3.2" fill="{accent}"/>
  </g>
"""


def architecture() -> str:
    """Return the layered architecture schema."""
    g1, g2, g3 = "#7C5CFF", "#12B5C9", "#E0559F"
    cw, ch = 1200, 860
    parts: list[str] = []

    parts.append(
        card(
            420,
            34,
            360,
            74,
            "Scenario",
            "parameters · seed · config",
            g1,
            mono=True,
            detail="class MyScenario(Scenario)",
        )
    )
    parts.append(flow((600, 108), (600, 168), g1, 2.6))

    parts.append("""  <g>
    <rect x="60" y="168" width="1080" height="196" rx="20" fill="#FBFAFF" stroke="#E6E3FB" stroke-width="1.3"/>
    <rect x="60" y="168" width="1080" height="38" rx="20" fill="#F3F0FF"/>
    <rect x="60" y="186" width="1080" height="20" fill="#F3F0FF"/>
    <text x="86" y="193" font-family="'JetBrains Mono', ui-monospace, monospace" font-size="13" font-weight="600" fill="#5B4BD6" letter-spacing="1.6">MODEL  ·  state · random · rng · time</text>
  </g>""")
    parts.append(
        card(
            84,
            224,
            320,
            104,
            "AgentSet",
            "agents · do · groupby",
            "#7C5CFF",
            detail="self.agents.shuffle_do()",
        )
    )
    parts.append(
        card(
            440,
            224,
            320,
            104,
            "Space",
            "grids · cells · networks",
            "#12B5C9",
            detail="OrthogonalMooreGrid",
        )
    )
    parts.append(
        card(
            796,
            224,
            320,
            104,
            "Time",
            "events · generators",
            "#E0559F",
            detail="EventList · Schedule",
        )
    )

    parts.append(flow((600, 364), (600, 424), g2, 3.0))
    parts.append(
        card(
            360,
            424,
            480,
            74,
            "DataRecorder · DataCollector",
            "tables · reporters · intervals",
            g2,
            mono=True,
            card_bg="#F7FDFE",
            card_edge="#CDEBF0",
        )
    )

    parts.append(flow((600, 498), (600, 558), g2, 3.0))
    parts.append(
        card(
            360,
            558,
            480,
            74,
            "Dataset",
            "pandas DataFrame · tidy rows",
            g2,
            mono=True,
            card_bg="#F7FDFE",
            card_edge="#CDEBF0",
        )
    )

    parts.append(flow((470, 632), (250, 704), g3, 3.2, 0.4, curve=-30))
    parts.append(flow((600, 632), (600, 704), g3, 3.2, 0.9))
    parts.append(flow((730, 632), (950, 704), g3, 3.2, 1.4, curve=30))

    parts.append(
        card(
            80,
            704,
            340,
            96,
            "Visualize",
            "Solara app · browser · Jupyter",
            g3,
            card_bg="#FFF7FB",
            card_edge="#F3D6E6",
        )
    )
    parts.append(
        card(
            430,
            704,
            340,
            96,
            "Analyze",
            "pandas · numpy · statistics",
            g3,
            card_bg="#FFF7FB",
            card_edge="#F3D6E6",
        )
    )
    parts.append(
        card(
            780,
            704,
            340,
            96,
            "Reproduce",
            "seeded runs · scenarios",
            g3,
            card_bg="#FFF7FB",
            card_edge="#F3D6E6",
        )
    )

    parts.append("""  <g>
    <path d="M1120 752 C1190 752 1190 300 1140 282" fill="none" stroke="#7C5CFF" stroke-opacity="0.5" stroke-width="1.8" stroke-dasharray="6 8" stroke-linecap="round"/>
    <circle cx="1140" cy="282" r="3.6" fill="#7C5CFF"/>
    <text x="1058" y="524" text-anchor="middle" font-family="'JetBrains Mono', ui-monospace, monospace" font-size="12" fill="#7A76A8" letter-spacing="1">next tick</text>
  </g>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cw} {ch}" width="{cw}" height="{ch}" role="img" aria-label="Modelly architecture: a scenario configures the model, which runs agents in a space on a schedule, records data into datasets and is explored through visualization and analysis.">
  <title>Modelly architecture</title>
{os_lines(parts)}
</svg>
"""


def os_lines(parts: list[str]) -> str:
    """Join generated SVG fragments into one document body."""
    return "\n".join(parts)


def simulation_loop() -> str:
    """Ring diagram of the step loop."""
    cw, ch = 1000, 560
    cx, cy, r = 500, 285, 142

    stations = [
        ("1 · Scenario", "n · width · seed", cx, cy - r - 96, "#7C5CFF"),
        ("2 · Step", "agents act", cx + r + 200, cy, "#12B5C9"),
        ("3 · Record", "collect metrics", cx, cy + r + 96, "#E0559F"),
        ("4 · Visualize", "explore results", cx - r - 200, cy, "#E8A020"),
    ]

    body: list[str] = []
    body.append(
        f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#EDEAFB" stroke-width="24"/>'
    )
    body.append(
        f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#7C5CFF" stroke-opacity="0.28" '
        f'stroke-width="2" stroke-dasharray="4 10"/>'
    )
    body.append(
        f'  <g transform="translate({cx} {cy})">'
        f'<circle r="{r}" fill="none" stroke="url(#ring)" stroke-width="6" stroke-linecap="round" '
        f'stroke-dasharray="{2 * math.pi * r * 0.24:.0f} {2 * math.pi * r:.0f}" transform="rotate(-60)"/>'
        f"</g>"
    )
    body.append(
        f'  <text x="{cx}" y="{cy - 4}" text-anchor="middle" font-family="{FONT}" font-size="28" font-weight="700" fill="#141833">one tick</text>'
    )
    body.append(
        f'  <text x="{cx}" y="{cy + 24}" text-anchor="middle" font-family="{MONO}" font-size="13.5" fill="#6B6F96">model.step()</text>'
    )

    for name, sub, x, y, acc in stations:
        body.append(
            f'  <g><rect x="{x - 118}" y="{y - 34}" width="236" height="68" rx="14" fill="#FFFFFF" '
            f'stroke="#E4E2F5" stroke-width="1.2"/>'
            f'<rect x="{x - 118}" y="{y - 34}" width="4" height="68" rx="2" fill="{acc}"/>'
            f'<text x="{x - 100}" y="{y - 6}" font-family="{FONT}" font-size="17" font-weight="600" fill="#141833">{name}</text>'
            f'<text x="{x - 100}" y="{y + 16}" font-family="{MONO}" font-size="12.5" fill="#6B6F96">{sub}</text>'
            f'<circle cx="{x + 98}" cy="{y}" r="4" fill="{acc}"/></g>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cw} {ch}" width="{cw}" height="{ch}" role="img" aria-label="The Modelly simulation loop: scenario, step, record, visualize.">
  <title>The Modelly simulation loop</title>
  <defs>
    <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#7C5CFF"/>
      <stop offset="0.5" stop-color="#12B5C9"/>
      <stop offset="1" stop-color="#E0559F"/>
    </linearGradient>
  </defs>
{os_lines(body)}
</svg>
"""


def main() -> None:
    """Write every brand asset into docs/images/branding/."""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "banner-dark.svg").write_text(banner(DARK, "dark"), encoding="utf-8")
    (OUT / "banner-light.svg").write_text(banner(LIGHT, "light"), encoding="utf-8")
    (OUT / "architecture.svg").write_text(architecture(), encoding="utf-8")
    (OUT / "simulation-loop.svg").write_text(simulation_loop(), encoding="utf-8")
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.relative_to(OUT.parents[2])}  {f.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
