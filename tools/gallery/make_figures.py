"""Draw the gallery figures: one small PNG per zoo model, in docs/images/gallery.

Each model's panel is ``tools/gallery/panels/<name>.py`` with a ``draw(ax)`` function that
runs the model (seeded, a few seconds at most) and plots one figure on ``ax``. Run from the
repository root, on any OS:

    python tools/gallery/make_figures.py              every model
    python tools/gallery/make_figures.py age_seir     only these

The PNGs are committed; rerun after changing a model or a panel.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))  # the checkout's modelly, installed or not

from modelly.zoo.registry import names  # noqa: E402

PANELS = HERE / "panels"
OUTPUT = ROOT / "docs" / "images" / "gallery"
SIZE = (4.0, 2.6)  # inches
DPI = 100
STYLE = {
    "font.size": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 9,
}


def load_panel(name: str):
    """Import ``panels/<name>.py`` as a module."""
    spec = importlib.util.spec_from_file_location(
        f"panel_{name}", PANELS / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make(name: str) -> Path:
    """Draw one model's panel and write ``<name>.png``."""
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=SIZE, layout="constrained")
        load_panel(name).draw(ax)
        path = OUTPUT / f"{name}.png"
        fig.savefig(path, dpi=DPI)
        plt.close(fig)
    return path


def main(argv: list[str]) -> int:
    """Draw the named panels, or all of them."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in argv or names():
        path = make(name)
        sys.stdout.write(f"wrote {path.relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
