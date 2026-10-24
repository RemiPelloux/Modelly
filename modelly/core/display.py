"""Rich display of a ``Model`` in Jupyter: class, scenario, time and population by class.

``Model._repr_html_`` and ``Model._repr_markdown_`` call these. They read only counters
the model already keeps (the per-class agent sets and their sizes), so displaying a model
of a million agents costs no more than displaying one of ten.
"""

from __future__ import annotations

import html
from typing import Any

MAX_PARAMS = 12  # scenario parameters shown; the rest are counted
MAX_VALUE = 40  # characters of one parameter's repr
ELLIPSIS = "..."


def short(value: Any) -> str:
    """``repr(value)`` cut to MAX_VALUE characters."""
    text = repr(value)
    if len(text) <= MAX_VALUE:
        return text
    return text[: MAX_VALUE - len(ELLIPSIS)] + ELLIPSIS


def parameters(model: Any) -> str:
    """The scenario's class and parameters, ``Name(n=100, width=10)``."""
    scenario = getattr(model, "scenario", None)
    if scenario is None:
        return "none"
    items = list(scenario)
    shown = ", ".join(f"{key}={short(value)}" for key, value in items[:MAX_PARAMS])
    hidden = len(items) - MAX_PARAMS
    more = f", ... {hidden} more" if hidden > 0 else ""
    seed = short(scenario.seed_sequence.entropy)
    return f"{type(scenario).__name__}({shown}{more}), seed {seed}"


def population(model: Any) -> list[tuple[str, int]]:
    """(agent class name, count) for every class with agents, largest first."""
    counts = [
        (cls.__name__, len(agents)) for cls, agents in model.agents_by_type.items()
    ]
    return sorted(counts, key=lambda row: (-row[1], row[0]))


def rows(model: Any) -> list[tuple[str, str]]:
    """The (label, value) lines shared by the HTML and Markdown views."""
    by_class = population(model)
    total = sum(count for _, count in by_class)
    breakdown = ", ".join(f"{name}: {count}" for name, count in by_class)
    return [
        ("time", short(model.time)),
        ("scenario", parameters(model)),
        ("agents", f"{total}" + (f" ({breakdown})" if breakdown else "")),
        ("running", str(model.running)),
    ]


def model_html(model: Any) -> str:
    """An HTML table of ``rows``, with the model's class as its caption."""
    body = "".join(
        f"<tr><th style='text-align:left'>{html.escape(label)}</th>"
        f"<td style='text-align:left'>{html.escape(value)}</td></tr>"
        for label, value in rows(model)
    )
    caption = html.escape(type(model).__name__)
    return f"<table><caption><b>{caption}</b></caption>{body}</table>"


def model_markdown(model: Any) -> str:
    """A Markdown list of ``rows`` under the model's class name."""
    lines = [f"**{type(model).__name__}**", ""]
    lines += [f"- **{label}**: {value}" for label, value in rows(model)]
    return "\n".join(lines)
