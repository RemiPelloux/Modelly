"""Tests for animation export and the headless space figure."""

import numpy as np
import pytest
from PIL import Image

from modelly.examples import BoidFlockers, BoltzmannWealth, VirusOnNetwork, WolfSheep
from modelly.examples.advanced.wolf_sheep.model import WolfSheepScenario
from modelly.timetravel import Recorder
from modelly.viz.animation import (
    MACRO_BLOCK,
    AnimationOptions,
    _pad,
    frames_from_run,
    frames_from_timeline,
    save_animation,
)
from modelly.viz.mpl.figure import can_draw, figure_pixels, space_figure

SMALL = AnimationOptions(fps=5, figsize=(2.0, 2.0), dpi=50)


@pytest.mark.parametrize("cls", [BoltzmannWealth, VirusOnNetwork, BoidFlockers])
def test_gif_of_a_grid_a_network_and_a_continuous_space(cls, tmp_path):
    """A GIF of each kind of space, one frame per step plus the first."""
    path = tmp_path / "run.gif"
    assert save_animation(frames_from_run(cls(), steps=3), path, SMALL) == 4
    with Image.open(path) as image:
        # Pillow merges identical consecutive frames (the network's agents do not move).
        assert 1 <= image.n_frames <= 4
        assert image.info.get("loop") == 0


def test_gif_without_loop(tmp_path):
    """loop=False writes a GIF that plays once."""
    path = tmp_path / "once.gif"
    options = AnimationOptions(fps=5, figsize=(2.0, 2.0), dpi=50, loop=False)
    save_animation(frames_from_run(BoltzmannWealth(), steps=1), path, options)
    with Image.open(path) as image:
        assert "loop" not in image.info


def test_mp4(tmp_path):
    """An MP4 through imageio-ffmpeg's bundled ffmpeg."""
    pytest.importorskip("imageio_ffmpeg")
    path = tmp_path / "run.mp4"
    assert save_animation(frames_from_run(BoltzmannWealth(), steps=4), path, SMALL) == 5
    assert path.stat().st_size > 0
    assert b"ftyp" in path.read_bytes()[:64]


def test_mp4_without_frames_writes_nothing(tmp_path):
    """No frames, no file."""
    pytest.importorskip("imageio_ffmpeg")
    assert save_animation(iter(()), tmp_path / "none.mp4") == 0
    assert save_animation(iter(()), tmp_path / "none.gif") == 0


def test_frames_from_a_timeline(tmp_path):
    """Frames of a recorded run, one per checkpoint."""
    model = WolfSheep(WolfSheepScenario(rng=1))
    with Recorder(model, every=2) as recorder:
        model.run_for(6)
    frames = list(frames_from_timeline(recorder))
    assert [frame.time for frame in frames] == [0.0, 2.0, 4.0, 6.0]
    assert save_animation(iter(frames), tmp_path / "run.gif", SMALL) == 4


def test_frames_every_and_stop():
    """``every`` skips frames; a stopped model ends the run."""
    model = BoltzmannWealth()
    assert [m.time for m in frames_from_run(model, steps=6, every=3)] == [0.0, 3.0, 6.0]
    model.running = False
    assert len(list(frames_from_run(model, steps=5))) == 1


def test_unknown_format(tmp_path):
    """Only .gif and .mp4 are written."""
    with pytest.raises(ValueError, match="unknown animation format"):
        save_animation(frames_from_run(BoltzmannWealth(), 1), tmp_path / "run.avi")


def test_frames_are_padded_to_macro_blocks():
    """Video frames are padded with white to a multiple of 16 pixels."""
    padded = _pad(np.zeros((17, 30, 3), dtype=np.uint8))
    assert padded.shape == (2 * MACRO_BLOCK, 2 * MACRO_BLOCK, 3)
    assert padded[-1, -1].tolist() == [255, 255, 255]


def test_space_figure_has_a_fixed_pixel_size():
    """The figure renders to the same size every step, as video needs."""
    model = BoltzmannWealth()
    first = figure_pixels(space_figure(model, figsize=(2.0, 3.0), dpi=40))
    model.run_for(2)
    second = figure_pixels(space_figure(model, figsize=(2.0, 3.0), dpi=40))
    assert first.shape == second.shape == (120, 80, 3)


def test_can_draw():
    """Models without a space, or with one Modelly cannot draw, are reported."""
    model = BoltzmannWealth()
    assert can_draw(model)
    model.grid = None
    assert not can_draw(model)
    model.grid = object()
    assert not can_draw(model)
