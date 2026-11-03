"""A report of a Studio session, to hand to someone who will not open Studio.

``report_html(session)`` is one self-contained HTML file (figures embedded as PNG): the
model, its parameters and seed, a figure of every model reporter, their final values, the
comparison of scenarios when there is one, the model card when the model has one, and the
run's manifest (Modelly and Python versions, the digest of the model's source, the steps
run), so a reader knows exactly which run the numbers come from. ``report_pdf`` holds the
same, one figure per page.
"""

from __future__ import annotations

import base64
import html
import io
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any

import modelly
from modelly.card import card_markdown, read_card

if TYPE_CHECKING:
    from modelly.decide.compare import Comparison
    from modelly.studio.session import StudioSession

CARD_FILE = "card.toml"
STYLE = ("body{font-family:system-ui,sans-serif;max-width:56rem;margin:2rem auto;padding:0 1rem;"
         "line-height:1.5}table{border-collapse:collapse}td,th{border:1px solid #bbb;"
         "padding:.2rem .5rem;text-align:left}img{max-width:100%}code{background:#eee}")  # fmt: skip


def card_path(target: str) -> Path | None:
    """The model card of ``target``: ``card.toml`` next to its file, or its zoo card."""
    source = target.rpartition(":")[0]
    if source.endswith(".py"):
        path = Path(source).parent / CARD_FILE
        return path if path.is_file() else None
    from modelly.zoo.registry import MODELS  # noqa: PLC0415

    return next((m.card for m in MODELS if m.module == source), None)


def manifest(session: StudioSession) -> dict[str, str]:
    """Which run the report shows: versions, model, source digest, seed and steps."""
    from modelly.provenance.files import hash_file  # noqa: PLC0415

    source = session.source_file()
    return {
        "modelly": modelly.__version__, "python": platform.python_version(),
        "model": session.config.target, "seed": str(session.seed),
        "steps run": f"{session.model.time:g}",
        "source sha256": hash_file(source) if source is not None else "not a file",
    }  # fmt: skip


def series_figures(session: StudioSession) -> list[tuple[str, bytes]]:
    """One PNG per model reporter: its series over the run."""
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    frame = session.model.datacollector.get_model_vars_dataframe()
    out = []
    for name in frame.select_dtypes("number").columns:
        figure, axes = plt.subplots(figsize=(6, 2.6), layout="constrained")
        axes.plot(frame.index, frame[name])
        axes.set_xlabel("step")
        axes.set_ylabel(name)
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", dpi=100)
        plt.close(figure)
        out.append((name, buffer.getvalue()))
    return out


def _table(rows: list[tuple[Any, ...]], header: tuple[str, ...]) -> str:
    """An HTML table."""
    head = "".join(f"<th>{html.escape(h)}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<table><tr>{head}</tr>{body}</table>"


def markdown_html(text: str) -> str:
    """The Markdown of a model card as HTML: headings, lists, tables, paragraphs."""
    out, rows = [], []
    for line in [*text.splitlines(), ""]:
        if line.startswith("|"):
            cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
            if not set("".join(cells)) <= set("-: "):
                rows.append(tuple(cells))
            continue
        if rows:
            out.append(_table(rows[1:], rows[0]))
            rows = []
        level = len(line) - len(line.lstrip("#"))
        if level and line[level:].startswith(" "):
            out.append(f"<h{level + 1}>{html.escape(line[level + 1 :])}</h{level + 1}>")
        elif line.startswith("- "):
            out.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip():
            out.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(out)


def _comparison_html(comparison: Comparison, output: str) -> str:
    """The ranking and the paired differences of a comparison."""
    rank = comparison.rank(output)
    diff = comparison.difference(output)
    rows = [(n, f"{r['mean']:.4g}", f"{r['low']:.4g} to {r['high']:.4g}",
             f"{diff.loc[n, 'mean']:.4g} ({diff.loc[n, 'low']:.4g} to {diff.loc[n, 'high']:.4g})",
             f"{r['best_share']:.0%}") for n, r in rank.iterrows()]  # fmt: skip
    header = (
        "scenario",
        output,
        "95% interval",
        f"minus {comparison.names[0]}",
        "lowest in",
    )
    return f"<h2>Scenarios compared</h2>{_table(rows, header)}"


def report_html(
    session: StudioSession,
    comparison: Comparison | None = None,
    output: str | None = None,
) -> str:
    """The session's report as one HTML document."""
    model = session.model
    title = f"{type(model).__name__}: a Modelly Studio report"
    parts = [f"<h1>{html.escape(title)}</h1>", "<h2>Parameters</h2>",
             _table(sorted(session.values.items()), ("parameter", "value"))]  # fmt: skip
    parts.append("<h2>Results</h2>")
    for name, png in series_figures(session):
        data = base64.b64encode(png).decode("ascii")
        parts.append(
            f'<h3>{html.escape(name)}</h3><img alt="{html.escape(name)} over the run" src="data:image/png;base64,{data}">'
        )
    if comparison is not None and output is not None:
        parts.append(_comparison_html(comparison, output))
    card = card_path(session.config.target)
    if card is not None:
        parts.append(markdown_html(card_markdown(read_card(card))))
    parts += [
        "<h2>Run manifest</h2>",
        _table(list(manifest(session).items()), ("", "")),
    ]
    body = "\n".join(parts)
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{STYLE}</style></head><body>{body}</body></html>\n'


def pdf_lines(session: StudioSession) -> list[str]:
    """The text of the PDF report: title, parameters, manifest, card."""
    lines = [f"{type(session.model).__name__}: a Modelly Studio report", ""]
    lines += [f"{k} = {v}" for k, v in sorted(session.values.items())] + [""]
    lines += [f"{k}: {v}" for k, v in manifest(session).items()]
    card = card_path(session.config.target)
    if card is not None:
        lines += ["", *card_markdown(read_card(card), references=False).splitlines()]
    return lines


def report_pdf(session: StudioSession, lines_per_page: int = 50) -> bytes:
    """The parameters, manifest and card as text pages, then one page per figure."""
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from matplotlib.backends.backend_pdf import PdfPages  # noqa: PLC0415

    lines, buffer = pdf_lines(session), io.BytesIO()
    with PdfPages(buffer) as pdf:
        for start in range(0, len(lines), lines_per_page):
            page = plt.figure(figsize=(8.27, 11.69))
            text = "\n".join(lines[start : start + lines_per_page])
            page.text(
                0.06, 0.96, text, va="top", family="monospace", fontsize=7, wrap=True
            )
            pdf.savefig(page)
            plt.close(page)
        for _, png in series_figures(session):
            page = plt.figure(figsize=(8.27, 4))
            page.figimage(plt.imread(io.BytesIO(png)), 20, 20)
            pdf.savefig(page)
            plt.close(page)
    return buffer.getvalue()
