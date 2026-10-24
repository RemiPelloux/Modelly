#!/usr/bin/env python3
"""Generate Modelly's animated SVG brand assets.

Run from the repository root:

    python tools/branding/generate_assets.py

Outputs (committed, served to GitHub via <picture> in README.md):

    docs/images/branding/banner-{dark,light}.svg
    docs/images/branding/architecture-{dark,light}.svg
    docs/images/branding/simulation-loop-{dark,light}.svg

Everything is hand-rolled SVG (CSS keyframes + SMIL), no external fonts,
no JavaScript, so it renders inside GitHub's <img> sandbox.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "images" / "branding"

FONT = "Inter, 'Segoe UI', 'Helvetica Neue', system-ui, -apple-system, sans-serif"
MONO = "'JetBrains Mono', 'SF Mono', ui-monospace, Menlo, monospace"

# Diagram palettes: one per colour scheme, so the architecture and loop diagrams
# stay readable on GitHub's light and dark themes (served through <picture>).
DIAGRAM_LIGHT = {
    "bg": "#FFFFFF",
    "panel": "#FBFAFF",
    "panel_edge": "#E6E3FB",
    "panel_head": "#F3F0FF",
    "panel_text": "#5B4BD6",
    "card": "#FFFFFF",
    "card_edge": "#E2E4F5",
    "title": "#0C1022",
    "sub": "#5A6183",
    "muted": "#7A76A8",
    "tint_teal": "#F7FDFE",
    "tint_teal_edge": "#CDEBF0",
    "tint_pink": "#FFF7FB",
    "tint_pink_edge": "#F3D6E6",
    "ring": "#EDEAFB",
    "ring_dash": "#7C5CFF",
    "center": "#141833",
    "center_sub": "#6B6F96",
}

DIAGRAM_DARK = {
    "bg": "#0B0F1F",
    "panel": "#121735",
    "panel_edge": "#2B3260",
    "panel_head": "#1A1F45",
    "panel_text": "#B9A8FF",
    "card": "#161B3A",
    "card_edge": "#2F3668",
    "title": "#F2F4FF",
    "sub": "#B3BADC",
    "muted": "#9AA1C8",
    "tint_teal": "#0F2430",
    "tint_teal_edge": "#1F4E5C",
    "tint_pink": "#2B1528",
    "tint_pink_edge": "#5E2C4C",
    "ring": "#1F2550",
    "ring_dash": "#9B7BFF",
    "center": "#F2F4FF",
    "center_sub": "#B3BADC",
}


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
    rnd = random.Random(11)
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
        dur = 5 + (k % 5) * 1.3
        edge_svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{p["edge"]}" stroke-opacity="{p["edge_op"]}" stroke-width="1.1" '
            f'stroke-dasharray="{dash} {dash + 5}" stroke-linecap="round">'
            f'<animate attributeName="stroke-dashoffset" from="0" to="-{2 * dash + 5}" '
            f'dur="{dur}s" repeatCount="indefinite"/></line>'
        )

    node_svg = []
    for x, y, rad in nodes:
        dx = round(rnd.uniform(-5, 5), 1)
        dy = round(rnd.uniform(-5, 5), 1)
        dur = round(rnd.uniform(5.5, 10.5), 1)
        delay = round(rnd.uniform(0, 3), 1)
        hub = rad > 4.2
        node_svg.append(
            f'<g><circle cx="{x}" cy="{y}" r="{rad}" fill="{p["node"]}"'
            + (' opacity="0.95"' if hub else ' opacity="0.8"')
            + ">"
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="0 0; {dx} {dy}; 0 0" dur="{dur}s" begin="-{delay}s" '
            f'repeatCount="indefinite" calcMode="spline" '
            f'keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/></circle>'
            + (
                f'<circle cx="{x}" cy="{y}" r="{rad * 3.2:.1f}" fill="none" '
                f'stroke="{p["node"]}" stroke-opacity="0.18" stroke-width="1">'
                f'<animate attributeName="r" values="{rad * 2:.1f};{rad * 3.6:.1f};{rad * 2:.1f}" '
                f'dur="{dur + 1}s" begin="-{delay}s" repeatCount="indefinite"/>'
                f'<animate attributeName="stroke-opacity" values="0.22;0.04;0.22" '
                f'dur="{dur + 1}s" begin="-{delay}s" repeatCount="indefinite"/></circle>'
                if hub
                else ""
            )
            + "</g>"
        )

    # two pulses travelling across the lattice
    pulse_paths = []
    for a, b in [(0, 5), (5, 23), (12, 17)]:
        (x1, y1, _), (x2, y2, _) = nodes[a], nodes[b]
        pulse_paths.append(
            f'<path id="pp-{theme_name}-{a}-{b}" d="M{x1} {y1} L{x2} {y2}" fill="none" '
            f'stroke="none"/>'
            f'<circle r="2.6" fill="{p["g2"]}" opacity="0">'
            f'<animateMotion dur="{rnd.uniform(4.5, 7):.1f}s" repeatCount="indefinite">'
            f'<mpath href="#pp-{theme_name}-{a}-{b}"/></animateMotion></circle>'
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
    <style>
      @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
      .blob {{ animation: drift 18s cubic-bezier(0.45,0,0.55,1) infinite alternate; }}
      @keyframes drift {{
        0%   {{ transform: translate3d(0,0,0) scale(1); opacity: 0.85; }}
        50%  {{ transform: translate3d(26px,-18px,0) scale(1.08); opacity: 1; }}
        100% {{ transform: translate3d(-18px,14px,0) scale(0.96); opacity: 0.8; }}
      }}
      .sheen {{ animation: sheen 7.5s ease-in-out infinite; }}
      @keyframes sheen {{
        0%   {{ transform: translateX(-520px); opacity: 0; }}
        12%  {{ opacity: 0.9; }}
        55%  {{ opacity: 0.9; }}
        70%, 100% {{ transform: translateX(1180px); opacity: 0; }}
      }}
      .caret {{ animation: blink 1.6s steps(1,end) infinite; }}
      @keyframes blink {{ 0%,55% {{ opacity: 1; }} 56%,100% {{ opacity: 0.15; }} }}
    </style>
  </defs>

  <g clip-path="url(#frame-{theme_name})">
    <rect width="1200" height="340" fill="url(#bg-{theme_name})"/>
    <rect width="1200" height="340" fill="url(#dots-{theme_name})"/>

    <g filter="url(#soft-{theme_name})">
      <ellipse class="blob" cx="180" cy="60" rx="230" ry="170" fill="url(#glow1-{theme_name})"/>
      <ellipse class="blob" cx="470" cy="300" rx="250" ry="180" fill="url(#glow2-{theme_name})" style="animation-delay:-6s"/>
      <ellipse class="blob" cx="1010" cy="250" rx="260" ry="200" fill="url(#glow3-{theme_name})" style="animation-delay:-11s"/>
    </g>

    <g>
      {"".join(edge_svg)}
      {"".join(node_svg)}
      {"".join(pulse_paths)}
    </g>

    <g>
      <rect x="78" y="56" width="216" height="34" rx="17" fill="{p["pill_bg"]}" stroke="{p["pill_stroke"]}" stroke-width="1"/>
      <circle cx="98" cy="73" r="3.4" fill="{p["g2"]}">
        <animate attributeName="opacity" values="1;0.25;1" dur="2.4s" repeatCount="indefinite"/>
      </circle>
      <text x="112" y="78" font-family="{MONO}" font-size="14" fill="{p["pill_text"]}" letter-spacing="0.6">open source · stable</text>
    </g>

    <text x="78" y="196" font-family="{FONT}" font-size="96" font-weight="700" letter-spacing="-3" fill="url(#word-{theme_name})">Modelly</text>

    <g clip-path="url(#wordclip-{theme_name})">
      <rect class="sheen" x="0" y="100" width="260" height="120" fill="url(#sheen-{theme_name})" fill-opacity="0.5" transform="skewX(-18)"/>
    </g>

    <text x="82" y="248" font-family="{FONT}" font-size="26" font-weight="400" fill="{p["sub"]}" letter-spacing="0.2">Agent-based modeling in Python<tspan class="caret" fill="{p["g2"]}">_</tspan></text>

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
    t: dict,
    *,
    card_bg: str | None = None,
    card_edge: str | None = None,
    mono: bool = False,
    detail: str | None = None,
    glow_at: float | None = None,
) -> str:
    """Return one diagram card: accent rail, title, subtitle, optional detail and arrival glow."""
    card_bg = card_bg or t["card"]
    card_edge = card_edge or t["card_edge"]
    title_color, sub_color = t["title"], t["sub"]
    extra = (
        f'\n    <text x="{x + 22}" y="{y + 82}" font-family="{MONO}" font-size="11.5" '
        f'fill="{accent}" fill-opacity="0.85">{detail}</text>'
        if detail
        else ""
    )
    flash = glow(x, y, w, h, accent, glow_at) if glow_at is not None else ""
    return f"""  <g>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{card_bg}" stroke="{card_edge}" stroke-width="1.2"/>
{flash}    <rect x="{x}" y="{y}" width="4" height="{h}" rx="2" fill="{accent}"/>
    <text x="{x + 22}" y="{y + 32}" font-family="{MONO if mono else FONT}" font-size="{14 if mono else 17}" font-weight="600" fill="{title_color}">{title}</text>
    <text x="{x + 22}" y="{y + 56}" font-family="{MONO}" font-size="12.5" fill="{sub_color}">{subtitle}</text>{extra}
  </g>
"""


TICK = 9.0  # seconds: one full trip of the token around the architecture diagram


def token(path_id: str, accent: str, begin: float, travel: float) -> str:
    """A pulse that travels ``path_id`` during its slot of the TICK cycle, hidden otherwise."""
    t0, t1 = begin / TICK, (begin + travel) / TICK
    fade = 0.02
    return f"""    <circle r="3.4" fill="{accent}" opacity="0">
      <animateMotion dur="{TICK}s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;{t0:.3f};{t1:.3f};1" calcMode="spline" keySplines="0 0 1 1;0.4 0 0.2 1;0 0 1 1">
        <mpath href="#{path_id}"/>
      </animateMotion>
      <animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;{t0:.3f};{min(t0 + fade, t1):.3f};{max(t1 - fade, t0):.3f};{t1:.3f};1" dur="{TICK}s" repeatCount="indefinite"/>
    </circle>
"""


def glow(
    x: float, y: float, w: float, h: float, accent: str, at: float, twice: bool = False
) -> str:
    """A soft flash of ``accent`` over a card when the token arrives at second ``at``."""
    a = at / TICK
    keys = f"0;{a:.3f};{a + 0.02:.3f};{a + 0.12:.3f};1"
    values = "0;0;0.16;0;0"
    if twice:  # the model panel is visited at the start and on the loop back
        b = (TICK - 1.4) / TICK
        keys = f"0;{a:.3f};{a + 0.02:.3f};{a + 0.12:.3f};{b:.3f};{b + 0.02:.3f};{b + 0.12:.3f};1"
        values = "0;0;0.16;0;0;0.16;0;0"
    return (
        f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{accent}" opacity="0">'
        f'<animate attributeName="opacity" values="{values}" keyTimes="{keys}" dur="{TICK}s" repeatCount="indefinite"/></rect>\n'
    )


def flow(
    a: tuple[float, float],
    b: tuple[float, float],
    accent: str,
    begin: float,
    travel: float = 0.8,
    curve: float = 0.0,
) -> str:
    """Dashed connector whose token travels from ``a`` to ``b`` at second ``begin`` of the tick."""
    x1, y1 = a
    x2, y2 = b
    mx = (x1 + x2) / 2 + curve
    my = (y1 + y2) / 2
    uid = f"f{int(x1)}-{int(y1)}-{int(x2)}-{int(y2)}"
    return f"""  <g>
    <path id="{uid}" d="M{x1} {y1} Q{mx} {my} {x2} {y2}" fill="none" stroke="{accent}" stroke-opacity="0.45" stroke-width="1.8" stroke-dasharray="5 7" stroke-linecap="round">
      <animate attributeName="stroke-dashoffset" from="0" to="-24" dur="3s" repeatCount="indefinite"/>
    </path>
{token(uid, accent, begin, travel)}  </g>
"""


def architecture(t: dict) -> str:
    """Return the layered architecture schema for one colour scheme."""
    g1, g2, g3 = "#7C5CFF", "#12B5C9", "#E0559F"
    cw, ch = 1200, 860
    parts: list[str] = [
        f'  <rect width="{cw}" height="{ch}" rx="24" fill="{t["bg"]}"/>'
    ]

    parts.append(
        card(
            420,
            34,
            360,
            74,
            "Scenario",
            "parameters · seed · config",
            g1,
            t,
            mono=True,
            detail="class MyScenario(Scenario)",
            glow_at=0.0,
        )
    )
    parts.append(flow((600, 108), (600, 168), g1, begin=0.2))

    parts.append(f"""  <g>
    <rect x="60" y="168" width="1080" height="196" rx="20" fill="{t["panel"]}" stroke="{t["panel_edge"]}" stroke-width="1.3"/>
    <rect x="60" y="168" width="1080" height="38" rx="20" fill="{t["panel_head"]}"/>
    <rect x="60" y="186" width="1080" height="20" fill="{t["panel_head"]}"/>
    <text x="86" y="193" font-family="'JetBrains Mono', ui-monospace, monospace" font-size="13" font-weight="600" fill="{t["panel_text"]}" letter-spacing="1.6">MODEL  ·  state · random · rng · time</text>
{glow(60, 168, 1080, 196, g1, 1.0, twice=True)}  </g>""")
    parts.append(
        card(
            84,
            224,
            320,
            104,
            "AgentSet",
            "agents · do · groupby",
            "#7C5CFF",
            t,
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
            t,
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
            t,
            detail="EventList · Schedule",
        )
    )

    parts.append(flow((600, 364), (600, 424), g2, begin=1.6))
    parts.append(
        card(
            360,
            424,
            480,
            74,
            "DataRecorder · DataCollector",
            "tables · reporters · intervals",
            g2,
            t,
            mono=True,
            card_bg=t["tint_teal"],
            card_edge=t["tint_teal_edge"],
            glow_at=2.4,
        )
    )

    parts.append(flow((600, 498), (600, 558), g2, begin=2.8))
    parts.append(
        card(
            360,
            558,
            480,
            74,
            "Dataset",
            "pandas DataFrame · tidy rows",
            g2,
            t,
            mono=True,
            card_bg=t["tint_teal"],
            card_edge=t["tint_teal_edge"],
            glow_at=3.6,
        )
    )

    parts.append(flow((470, 632), (250, 704), g3, begin=4.0, travel=1.0, curve=-30))
    parts.append(flow((600, 632), (600, 704), g3, begin=4.0, travel=1.0))
    parts.append(flow((730, 632), (950, 704), g3, begin=4.0, travel=1.0, curve=30))

    parts.append(
        card(
            80,
            704,
            340,
            96,
            "Visualize",
            "Solara app · browser · Jupyter",
            g3,
            t,
            card_bg=t["tint_pink"],
            card_edge=t["tint_pink_edge"],
            glow_at=5.0,
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
            t,
            card_bg=t["tint_pink"],
            card_edge=t["tint_pink_edge"],
            glow_at=5.0,
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
            t,
            card_bg=t["tint_pink"],
            card_edge=t["tint_pink_edge"],
            glow_at=5.0,
        )
    )

    parts.append(f"""  <g>
    <path id="loopback" d="M1120 752 C1190 752 1190 300 1140 282" fill="none" stroke="#7C5CFF" stroke-opacity="0.38" stroke-width="1.8" stroke-dasharray="6 8" stroke-linecap="round">
      <animate attributeName="stroke-dashoffset" from="0" to="-28" dur="3.4s" repeatCount="indefinite"/>
    </path>
{token("loopback", g1, 5.4, 2.2)}    <text x="1058" y="524" text-anchor="middle" font-family="'JetBrains Mono', ui-monospace, monospace" font-size="12" fill="{t["muted"]}" letter-spacing="1">next tick<animate attributeName="opacity" values="0.6;0.6;1;1;0.6;0.6" keyTimes="0;0.6;0.63;0.82;0.85;1" dur="{TICK}s" repeatCount="indefinite"/></text>
  </g>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cw} {ch}" width="{cw}" height="{ch}" role="img" aria-label="Modelly architecture: a scenario configures the model, which runs agents in a space on a schedule, records data into datasets and is explored through visualization and analysis.">
  <title>Modelly architecture</title>
  <defs>
    <style>
      @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
    </style>
  </defs>
{os_lines(parts)}
</svg>
"""


def os_lines(parts: list[str]) -> str:
    """Join generated SVG fragments into one document body."""
    return "\n".join(parts)


LOOP_TICK = 4.5  # seconds: one trip of the token around the tick ring
LOOP_TICKS = 4  # the centre counter shows ticks 1..LOOP_TICKS, then starts over
LOOP_W, LOOP_H = 1200, 510
RING_X, RING_Y, RING_R = 585, 300, 118

# (angle in degrees, clockwise from 12 o'clock) and text of each station on the ring.
LOOP_STATIONS = (
    (0, "agents act", 'agents.shuffle_do("step")', "#7C5CFF"),
    (120, "record", "datacollector.collect(self)", "#12B5C9"),
    (240, "time += 1", "due events fire", "#E0559F"),
)


def ring_point(angle: float, radius: float = RING_R) -> tuple[float, float]:
    """Point on the tick ring at ``angle`` degrees clockwise from 12 o'clock."""
    rad = math.radians(angle - 90)
    return RING_X + radius * math.cos(rad), RING_Y + radius * math.sin(rad)


def loop_heading(x: float, text: str, t: dict) -> str:
    """Small caps column heading: before the run, every tick, after the run."""
    return (
        f'  <text x="{x}" y="58" text-anchor="middle" font-family="{MONO}" font-size="12" '
        f'font-weight="600" letter-spacing="2" fill="{t["muted"]}">{text}</text>'
    )


def loop_card(x: float, y: float, title: str, code: str, accent: str, t: dict) -> str:
    """One static card in the before / after columns."""
    return (
        f'  <g><rect x="{x}" y="{y}" width="232" height="70" rx="14" fill="{t["card"]}" '
        f'stroke="{t["card_edge"]}" stroke-width="1.2"/>'
        f'<rect x="{x}" y="{y}" width="4" height="70" rx="2" fill="{accent}"/>'
        f'<text x="{x + 20}" y="{y + 30}" font-family="{FONT}" font-size="17" font-weight="600" fill="{t["title"]}">{title}</text>'
        f'<text x="{x + 20}" y="{y + 52}" font-family="{MONO}" font-size="12" fill="{t["sub"]}">{code}</text></g>'
    )


def loop_arrow(d: str, label: str, lx: float, ly: float, t: dict) -> str:
    """Dashed one-way connector with a flowing dash and a small label."""
    return (
        f'  <path d="{d}" fill="none" stroke="{t["ring_dash"]}" stroke-opacity="0.55" stroke-width="1.8" '
        f'stroke-dasharray="5 6" marker-end="url(#head)">'
        f'<animate attributeName="stroke-dashoffset" from="22" to="0" dur="1.6s" repeatCount="indefinite"/></path>\n'
        f'  <text x="{lx}" y="{ly}" text-anchor="middle" font-family="{MONO}" font-size="11.5" fill="{t["muted"]}">{label}</text>'
    )


def pulse(begin: float, attr: str, rest: str, peak: str) -> str:
    """Animate ``attr`` up to ``peak`` when the token reaches a station, once per tick."""
    return (
        f'<animate attributeName="{attr}" values="{rest};{peak};{rest};{rest}" keyTimes="0;0.06;0.3;1" '
        f'dur="{LOOP_TICK}s" begin="{begin:.2f}s" repeatCount="indefinite"/>'
    )


def loop_station(angle: float, title: str, code: str, accent: str, t: dict) -> str:
    """A node on the ring that lights up as the token passes, with its label outside."""
    nx, ny = ring_point(angle)
    lx, ly = ring_point(angle, RING_R + 34)
    anchor = "middle" if angle == 0 else ("start" if angle < 180 else "end")
    ty = ly - 26 if angle == 0 else ly + 10
    begin = angle / 360 * LOOP_TICK
    return (
        f'  <g><circle cx="{nx:.1f}" cy="{ny:.1f}" r="16" fill="{accent}" opacity="0">{pulse(begin, "opacity", "0", "0.25")}</circle>'
        f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="7" fill="{t["bg"]}" stroke="{accent}" stroke-width="3"/>'
        f'<text x="{lx:.1f}" y="{ty:.1f}" text-anchor="{anchor}" font-family="{FONT}" font-size="17" font-weight="600" '
        f'fill="{t["title"]}" fill-opacity="0.55">{title}{pulse(begin, "fill-opacity", "0.55", "1")}</text>'
        f'<text x="{lx:.1f}" y="{ty + 21:.1f}" text-anchor="{anchor}" font-family="{MONO}" font-size="12" '
        f'fill="{accent}">{code}</text></g>'
    )


def tick_counter(t: dict) -> str:
    """Centre label: the tick number steps up once per trip of the token."""
    out = []
    for k in range(LOOP_TICKS):
        values = ";".join("1" if i == k else "0" for i in range(LOOP_TICKS))
        keys = ";".join(f"{i / LOOP_TICKS:.3f}" for i in range(LOOP_TICKS))
        out.append(
            f'  <text x="{RING_X}" y="{RING_Y + 40}" text-anchor="middle" font-family="{MONO}" font-size="13.5" '
            f'fill="{t["center_sub"]}" opacity="{1 if k == 0 else 0}">model.time = {k + 1}'
            f'<animate attributeName="opacity" values="{values}" keyTimes="{keys}" calcMode="discrete" '
            f'dur="{LOOP_TICK * LOOP_TICKS}s" repeatCount="indefinite"/></text>'
        )
    return "\n".join(out)


def loop_ring(t: dict) -> str:
    """The tick ring, its travelling token and the centre labels."""
    top_x, top_y = ring_point(0)
    bot_x, bot_y = ring_point(180)
    path = f"M{top_x} {top_y} A{RING_R} {RING_R} 0 0 1 {bot_x} {bot_y} A{RING_R} {RING_R} 0 0 1 {top_x} {top_y}"
    return f"""  <circle cx="{RING_X}" cy="{RING_Y}" r="{RING_R}" fill="none" stroke="{t["ring"]}" stroke-width="20"/>
  <path id="tick" d="{path}" fill="none" stroke="url(#ring)" stroke-width="2.5" stroke-opacity="0.7"/>
  <circle r="6" fill="#12B5C9"><animateMotion dur="{LOOP_TICK}s" repeatCount="indefinite"><mpath href="#tick"/></animateMotion></circle>
  <text x="{RING_X}" y="{RING_Y - 10}" text-anchor="middle" font-family="{FONT}" font-size="26" font-weight="700" fill="{t["center"]}">one tick</text>
  <text x="{RING_X}" y="{RING_Y + 14}" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{t["muted"]}">model.step()</text>
{tick_counter(t)}"""


def simulation_loop(t: dict) -> str:
    """Before the run, the per-tick ring, after the run: one diagram per colour scheme."""
    left, right = 40, LOOP_W - 272
    body = [
        f'  <rect width="{LOOP_W}" height="{LOOP_H}" rx="24" fill="{t["bg"]}"/>',
        loop_heading(left + 116, "BEFORE THE RUN", t),
        loop_heading(RING_X, "EVERY TICK", t),
        loop_heading(right + 116, "AFTER THE RUN", t),
        loop_card(left, 130, "Scenario", "WealthScenario(rng=42)", "#7C5CFF", t),
        loop_arrow(
            f"M{left + 116} 200 L{left + 116} 262", "configures", left + 170, 236, t
        ),
        loop_card(left, 265, "Model", "WealthModel(scenario)", "#7C5CFF", t),
        loop_arrow(
            f"M{left + 232} 300 L{RING_X - RING_R - 22} 300",
            "run",
            (left + 232 + RING_X - RING_R) / 2,
            290,
            t,
        ),
        loop_ring(t),
        *(
            loop_station(a, title, code, acc, t)
            for a, title, code, acc in LOOP_STATIONS
        ),
        loop_arrow(
            f"M{RING_X + RING_R + 22} 300 L{right} 300",
            "one row per tick",
            (RING_X + RING_R + right) / 2,
            290,
            t,
        ),
        loop_card(right, 265, "DataFrame", "get_model_vars_dataframe()", "#12B5C9", t),
        loop_arrow(
            f"M{right + 116} 335 L{right + 116} 397", "pandas", right + 160, 371, t
        ),
        loop_card(
            right, 400, "Visualize · Analyze", "Solara · plots · stats", "#E0559F", t
        ),
    ]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LOOP_W} {LOOP_H}" width="{LOOP_W}" height="{LOOP_H}" role="img" aria-label="The Modelly simulation loop: a scenario configures the model once; every tick the agents act, data is recorded and time advances; after the run the rows are a pandas DataFrame to visualize and analyze.">
  <title>The Modelly simulation loop</title>
  <defs>
    <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#7C5CFF"/>
      <stop offset="0.5" stop-color="#12B5C9"/>
      <stop offset="1" stop-color="#E0559F"/>
    </linearGradient>
    <marker id="head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 L10 5 L0 10 z" fill="{t["ring_dash"]}" fill-opacity="0.7"/>
    </marker>
  </defs>
{os_lines(body)}
</svg>
"""


def main() -> None:
    """Write every brand asset into docs/images/branding/."""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "banner-dark.svg").write_text(banner(DARK, "dark"), encoding="utf-8")
    (OUT / "banner-light.svg").write_text(banner(LIGHT, "light"), encoding="utf-8")
    for name, t in (("light", DIAGRAM_LIGHT), ("dark", DIAGRAM_DARK)):
        (OUT / f"architecture-{name}.svg").write_text(architecture(t), encoding="utf-8")
        (OUT / f"simulation-loop-{name}.svg").write_text(
            simulation_loop(t), encoding="utf-8"
        )
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.relative_to(OUT.parents[2])}  {f.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
