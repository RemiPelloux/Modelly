"""Solara based visualization for Modelly models.

The names below are imported on first access, so ``import modelly.viz.palettes`` (or any
other submodule) does not load Altair, Solara, Matplotlib's pyplot and NetworkX.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modelly._optional import lazy_exports

if TYPE_CHECKING:
    from modelly.viz.altair.components import make_space_altair
    from modelly.viz.components import make_plot_component, make_space_component
    from modelly.viz.console.console import CommandConsole
    from modelly.viz.mpl.space import draw_space
    from modelly.viz.render.renderer import SpaceRenderer
    from modelly.viz.solara.app import JupyterViz, SolaraViz
    from modelly.viz.solara.params import Slider

# Each public name and the module it lives in.
_MODULES = {
    "CommandConsole": "modelly.viz.console.console",
    "JupyterViz": "modelly.viz.solara.app",
    "Slider": "modelly.viz.solara.params",
    "SolaraViz": "modelly.viz.solara.app",
    "SpaceRenderer": "modelly.viz.render.renderer",
    "draw_space": "modelly.viz.mpl.space",
    "make_plot_component": "modelly.viz.components",
    "make_space_altair": "modelly.viz.altair.components",
    "make_space_component": "modelly.viz.components",
}

__all__ = [
    "CommandConsole",
    "JupyterViz",
    "Slider",
    "SolaraViz",
    "SpaceRenderer",
    "draw_space",
    "make_plot_component",
    "make_space_altair",
    "make_space_component",
]


__getattr__, __dir__ = lazy_exports(__name__, _MODULES)
