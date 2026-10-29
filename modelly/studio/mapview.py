"""The Map tab: the model's space drawn by WebGL in the browser, for large models.

``MapWidget`` is a Vue template (``map.vue``, shipped with Modelly: nothing comes from a
CDN) that uploads the arrays of ``modelly.studio.scene`` to the GPU and draws agents as
points, network edges and region outlines as lines, with pan and zoom. Where WebGL is not
available, the same template draws with Canvas 2D; the checkbox under the map forces that.
"""

from __future__ import annotations

import ipyvuetify
import solara
import traitlets

from modelly.studio.scene import encode, scene_of
from modelly.studio.state import StudioState
from modelly.viz.render.portrayal import ClassColours

DEFAULT_HEIGHT = 520
DEFAULT_POINT_SIZE = 4.0
POINT_SIZES = {"min": 1.0, "max": 12.0, "step": 0.5}
SWATCH = "display: inline-block; width: 12px; height: 12px; margin-right: 4px;"


class MapWidget(ipyvuetify.VuetifyTemplate):
    """The WebGL map: draws an ``encode``-d scene, pans and zooms in the browser."""

    template_file = (__file__, "map.vue")

    scene = traitlets.Dict({}).tag(sync=True)
    height = traitlets.Int(DEFAULT_HEIGHT).tag(sync=True)
    point_size = traitlets.Float(DEFAULT_POINT_SIZE).tag(sync=True)
    force_canvas = traitlets.Bool(False).tag(sync=True)


def _legend(legend: list[tuple[str, str]], portrayed: bool) -> None:
    """The agent classes and their colours, or a note that the portrayal colours them."""
    if portrayed:
        solara.Text("Colours from the portrayal.")
        return
    with solara.Row():
        for name, colour in legend:
            solara.HTML(
                tag="span",
                unsafe_innerHTML=f'<span style="{SWATCH} background: {colour}"></span>{name}',
            )


@solara.component
def MapView(state: StudioState):
    """The shown model's space, drawn in the browser by WebGL (Canvas 2D without it)."""
    state.revision.get()
    session = state.session
    size = solara.use_reactive(DEFAULT_POINT_SIZE)
    canvas = solara.use_reactive(False)
    default = isinstance(session.portrayal, ClassColours)
    portrayal = None if default else session.portrayal
    with session.lock:
        scene = scene_of(session.shown, portrayal)
    with solara.Card("Map (WebGL)"):
        if scene is None:
            solara.Text("This model has no space to draw.")
            return
        renderer = "canvas" if canvas.value else "webgl"
        MapWidget.element(
            scene=encode(scene), point_size=size.value, force_canvas=canvas.value
        ).key(f"map-{renderer}")
        _legend(scene.legend, scene.colours is not None)
        with solara.Row():
            solara.SliderFloat("point size", value=size, **POINT_SIZES)
            solara.Checkbox(label="Canvas 2D instead of WebGL", value=canvas)


__all__ = ["MapView", "MapWidget"]
