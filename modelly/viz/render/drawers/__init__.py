"""Modelly visualization space drawers.

This module provides the core logic for drawing spaces in Modelly, supporting
orthogonal grids, hexagonal grids, networks, continuous spaces, and Voronoi grids.
It includes implementations for both Matplotlib and Altair backends.

The drawers are imported on first use, so drawing a grid never loads NetworkX.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modelly._optional import lazy_exports

if TYPE_CHECKING:
    from modelly.viz.render.drawers.base import (
        BaseSpaceDrawer,
        HexGrid,
        Network,
        OrthogonalGrid,
    )
    from modelly.viz.render.drawers.continuous import ContinuousSpaceDrawer
    from modelly.viz.render.drawers.hexagonal import HexSpaceDrawer
    from modelly.viz.render.drawers.network import NetworkSpaceDrawer
    from modelly.viz.render.drawers.orthogonal import OrthogonalSpaceDrawer
    from modelly.viz.render.drawers.voronoi import VoronoiSpaceDrawer

_BASE = "modelly.viz.render.drawers.base"

__all__ = [
    "BaseSpaceDrawer",
    "ContinuousSpaceDrawer",
    "HexGrid",
    "HexSpaceDrawer",
    "Network",
    "NetworkSpaceDrawer",
    "OrthogonalGrid",
    "OrthogonalSpaceDrawer",
    "VoronoiSpaceDrawer",
]

__getattr__, __dir__ = lazy_exports(
    __name__,
    {
        "BaseSpaceDrawer": _BASE,
        "HexGrid": _BASE,
        "Network": _BASE,
        "OrthogonalGrid": _BASE,
        "ContinuousSpaceDrawer": "modelly.viz.render.drawers.continuous",
        "HexSpaceDrawer": "modelly.viz.render.drawers.hexagonal",
        "NetworkSpaceDrawer": "modelly.viz.render.drawers.network",
        "OrthogonalSpaceDrawer": "modelly.viz.render.drawers.orthogonal",
        "VoronoiSpaceDrawer": "modelly.viz.render.drawers.voronoi",
    },
)
