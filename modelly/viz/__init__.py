"""Solara based visualization for Modelly models."""

from modelly.viz.altair.components import make_space_altair
from modelly.viz.components import make_plot_component, make_space_component
from modelly.viz.console.console import CommandConsole
from modelly.viz.mpl.space import (
    draw_space,
)
from modelly.viz.render.renderer import SpaceRenderer
from modelly.viz.solara.app import JupyterViz, SolaraViz
from modelly.viz.solara.params import Slider

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
