"""What Studio's views and exports read from a model: series, agents, figures, files.

Plain functions of a model, so that the views, the exports and the tests share them.
"""

from __future__ import annotations

import importlib.util
import io
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from matplotlib.figure import Figure

from modelly.core.checkpoint import checkpoint_bytes
from modelly.timetravel.snapshot import agent_state
from modelly.viz.animation import AnimationOptions, save_animation
from modelly.viz.mpl.figure import can_draw, space_figure
from modelly.viz.palettes import OKABE_ITO

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.studio.session import StudioSession

ALL_CLASSES = "All"
FIGURE_FORMATS = ("png", "svg")
SERIES_FIGSIZE = (6.0, 4.0)
# An animation of the timeline samples at most this many steps.
MAX_FRAMES = 120


def model_series(model: Model) -> pd.DataFrame | None:
    """The numeric model reporters the ``DataCollector`` collected, or None."""
    collector = getattr(model, "datacollector", None)
    if collector is None or not getattr(collector, "model_reporters", None):
        return None
    frame = collector.get_model_vars_dataframe()
    numeric = frame.select_dtypes("number")
    return numeric if not numeric.empty else None


def series_figure(model: Model) -> Figure | None:
    """A line plot of every numeric model reporter, or None when there is none."""
    frame = model_series(model)
    if frame is None:
        return None
    figure = Figure(figsize=SERIES_FIGSIZE, layout="constrained")
    ax = figure.add_subplot()
    for index, column in enumerate(frame.columns):
        ax.plot(
            frame.index,
            frame[column],
            label=str(column),
            color=OKABE_ITO[index % len(OKABE_ITO)],
        )
    ax.set_xlabel("collection")
    ax.legend(loc="best", frameon=False)
    return figure


def agent_classes(model: Model) -> list[str]:
    """``All`` and the names of the agent classes present, sorted."""
    return [ALL_CLASSES, *sorted({type(agent).__name__ for agent in model.agents})]


def agent_table(
    model: Model, class_name: str = ALL_CLASSES, rows: int = 100
) -> pd.DataFrame:
    """The first ``rows`` agents (of ``class_name``) by ``unique_id``, one column per attribute."""
    agents = sorted(model.agents, key=lambda agent: agent.unique_id)
    if class_name != ALL_CLASSES:
        agents = [a for a in agents if type(a).__name__ == class_name]
    records = [
        {"unique_id": a.unique_id, "class": type(a).__name__, **agent_state(a)}
        for a in agents[:rows]
    ]
    frame = pd.DataFrame.from_records(records)
    # Tuples (cells, positions) as text, so the table widget shows them.
    return frame.map(lambda v: str(v) if isinstance(v, tuple) else v)


def figure_bytes(figure: Figure, fmt: str) -> bytes:
    """``figure`` saved as ``png`` or ``svg``.

    Raises:
        ValueError: For another format.
    """
    if fmt not in FIGURE_FORMATS:
        raise ValueError(f"figure format must be one of {FIGURE_FORMATS}, got {fmt!r}")
    buffer = io.BytesIO()
    figure.savefig(buffer, format=fmt, bbox_inches="tight")
    return buffer.getvalue()


def series_image(model: Model, fmt: str = "png") -> bytes | None:
    """The reporters plot as an image file, or None when nothing was collected."""
    figure = series_figure(model)
    return None if figure is None else figure_bytes(figure, fmt)


def space_image(session: StudioSession, fmt: str = "png") -> bytes | None:
    """The space view as shown, as an image file, or None when there is no space."""
    model = session.shown
    if not can_draw(model):
        return None
    return figure_bytes(space_figure(model, session.portrayal), fmt)


def parquet_available() -> bool:
    """Whether pyarrow is installed, so the data can be exported as Parquet."""
    return importlib.util.find_spec("pyarrow") is not None


def data_bytes(model: Model, fmt: str = "csv") -> bytes | None:
    """The collected model data as ``csv`` or ``parquet``, or None when none was collected."""
    collector = getattr(model, "datacollector", None)
    if collector is None:
        return None
    frame = collector.get_model_vars_dataframe()
    if fmt == "parquet":
        buffer = io.BytesIO()
        frame.to_parquet(buffer)
        return buffer.getvalue()
    return frame.to_csv().encode("utf-8")


def checkpoint_file(model: Model) -> bytes:
    """The model as a ``Model.load`` checkpoint.

    Raises:
        CheckpointError: When the model holds something that cannot be saved.
    """
    return checkpoint_bytes(model)


def timeline_steps(span: tuple[float, float]) -> list[float]:
    """The steps an animation of ``span`` shows: every step, sampled to ``MAX_FRAMES``."""
    first, last = span
    count = int(last - first) + 1
    stride = max(1, -(-count // MAX_FRAMES))
    return [first + index for index in range(0, count, stride)]


def replay_frames(timeline, steps: list[float]) -> Iterator[Model]:
    """One model restored at the first step and run on through ``steps``."""
    model = timeline.at(steps[0])
    for step in steps:
        if step > model.time:
            model.run_for(step - model.time)
        yield model


def animation_bytes(session: StudioSession, suffix: str = ".gif") -> bytes | None:
    """The recorded run's space view as a GIF or MP4, or None when there is no space."""
    if not can_draw(session.shown):
        return None
    models = replay_frames(session.timeline, timeline_steps(session.timeline.span))
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"run{suffix}"
        save_animation(models, path, AnimationOptions(), session.portrayal)
        return path.read_bytes()
