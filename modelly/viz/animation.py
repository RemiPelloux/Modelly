"""Export a space view as an animation (GIF or MP4), rendered headless.

The frames are models: the states of one run, one per frame. ``frames_from_run`` steps a
model and yields it after every ``every`` steps; ``frames_from_timeline`` yields the model
at each recorded step of a ``modelly.timetravel`` recording. ``save_animation`` draws each
one with ``modelly.viz.mpl.figure.space_figure`` and writes the file::

    from modelly.viz.animation import frames_from_run, save_animation

    save_animation(frames_from_run(model, steps=100), "run.mp4")

GIF needs only Pillow (a Matplotlib dependency). MP4 needs the ``video`` extra
(``pip install modelly-abm[video]``), whose ``imageio-ffmpeg`` ships an ffmpeg binary for
Windows, macOS and Linux: nothing to install system-wide.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from modelly.viz.mpl.figure import DEFAULT_DPI, figure_pixels, space_figure

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.timetravel import Timeline

DEFAULT_FPS = 10
MS_PER_SECOND = 1000
# Video codecs work on blocks of 16 pixels; frames are padded to a multiple of it.
MACRO_BLOCK = 16
WHITE = 255
FORMATS = (".gif", ".mp4")


@dataclass(frozen=True)
class AnimationOptions:
    """How an animation is drawn and timed.

    Attributes:
        fps: Frames per second.
        figsize: Width and height of each frame, in inches.
        dpi: Pixels per inch.
        loop: For GIF, play in a loop (MP4 players decide for themselves).
    """

    fps: int = DEFAULT_FPS
    figsize: tuple[float, float] = (5.0, 5.0)
    dpi: int = DEFAULT_DPI
    loop: bool = True


def frames_from_run(model: Model, steps: int, every: int = 1) -> Iterator[Model]:
    """Yield ``model`` now, then after every ``every`` steps, ``steps`` steps in all.

    The model is stepped in place; the run stops early when ``model.running`` is False.
    """
    yield model
    for done in range(1, steps + 1):
        if not model.running:
            return
        model.step()
        if done % every == 0:
            yield model


def frames_from_timeline(timeline: Timeline) -> Iterator[Model]:
    """Yield the model at each recorded step of ``timeline``, oldest first."""
    for step in timeline.steps:
        yield timeline.at(step)


def _pad(frame: np.ndarray) -> np.ndarray:
    """Pad a frame with white to a multiple of ``MACRO_BLOCK`` pixels each way."""
    height, width = frame.shape[:2]
    pad_h, pad_w = (-height) % MACRO_BLOCK, (-width) % MACRO_BLOCK
    return np.pad(frame, ((0, pad_h), (0, pad_w), (0, 0)), constant_values=WHITE)


def _write_gif(path: Path, frames: Iterator[np.ndarray], options) -> int:
    """Write the frames as a GIF with Pillow; the number of frames."""
    from PIL import Image  # noqa: PLC0415 (Pillow comes with Matplotlib)

    images = [Image.fromarray(frame) for frame in frames]
    if not images:
        return 0
    # loop=0 repeats forever; without the key the GIF plays once.
    looping = {"loop": 0} if options.loop else {}
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=MS_PER_SECOND // options.fps,
        **looping,
    )
    return len(images)


def _write_mp4(path: Path, frames: Iterator[np.ndarray], options) -> int:
    """Write the frames as an H.264 MP4 with imageio-ffmpeg; the number of frames."""
    try:
        import imageio_ffmpeg  # noqa: PLC0415 (optional: the video extra)
    except ImportError as error:
        raise ImportError(
            "MP4 export needs imageio-ffmpeg: pip install modelly-abm[video]"
        ) from error
    first = next(frames, None)
    if first is None:
        return 0
    height, width = first.shape[:2]
    writer = imageio_ffmpeg.write_frames(str(path), (width, height), fps=options.fps)
    writer.send(None)  # start ffmpeg
    count = 0
    try:
        for frame in (first, *frames):
            writer.send(np.ascontiguousarray(frame).tobytes())
            count += 1
    finally:
        writer.close()
    return count


def save_animation(
    models: Iterable[Model],
    path: str | Path,
    options: AnimationOptions | None = None,
    agent_portrayal: Callable | None = None,
) -> int:
    """Draw each model's space as one frame and write a GIF or MP4 to ``path``.

    Args:
        models: The frames, such as ``frames_from_run(...)`` or ``frames_from_timeline(...)``.
        path: The file; its suffix, ``.gif`` or ``.mp4``, picks the format.
        options: Frame rate, frame size and looping.
        agent_portrayal: As for ``space_figure``; one colour per agent class by default.

    Returns:
        The number of frames written.

    Raises:
        ValueError: For a suffix other than ``.gif`` and ``.mp4``.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in FORMATS:
        raise ValueError(f"unknown animation format {path.suffix!r}; use .gif or .mp4")
    options = options or AnimationOptions()
    frames = (
        _pad(
            figure_pixels(
                space_figure(model, agent_portrayal, options.figsize, options.dpi)
            )
        )
        for model in models
    )
    write = _write_gif if suffix == ".gif" else _write_mp4
    return write(path, frames, options)


__all__ = [
    "AnimationOptions",
    "frames_from_run",
    "frames_from_timeline",
    "save_animation",
]
