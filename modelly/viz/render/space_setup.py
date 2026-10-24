"""Pick the space drawer and backend for a space, and map agent coordinates."""

from modelly.space import VoronoiGrid
from modelly.space.continuous import ContinuousSpace
from modelly.viz.altair.backend import AltairBackend
from modelly.viz.mpl.backend import MatplotlibBackend
from modelly.viz.render.drawers.base import HexGrid, Network, OrthogonalGrid
from modelly.viz.render.drawers.continuous import ContinuousSpaceDrawer
from modelly.viz.render.drawers.hexagonal import HexSpaceDrawer
from modelly.viz.render.drawers.network import NetworkSpaceDrawer
from modelly.viz.render.drawers.orthogonal import OrthogonalSpaceDrawer
from modelly.viz.render.drawers.voronoi import VoronoiSpaceDrawer


def make_space_drawer(space):
    """Return the space drawer for the space's type.

    Raises:
        ValueError: If the space type is not supported.
    """
    if isinstance(space, HexGrid):
        return HexSpaceDrawer(space)
    elif isinstance(space, OrthogonalGrid):
        return OrthogonalSpaceDrawer(space)
    elif isinstance(space, ContinuousSpace):
        return ContinuousSpaceDrawer(space)
    elif isinstance(space, VoronoiGrid):
        return VoronoiSpaceDrawer(space)
    elif isinstance(space, Network):
        return NetworkSpaceDrawer(space)
    raise ValueError(
        f"Unsupported space type: {type(space).__name__}. "
        "Supported types are OrthogonalGrid, HexGrid, ContinuousSpace, VoronoiGrid, and Network."
    )


def make_backend(backend, space_drawer):
    """Return the backend renderer named by ``backend``.

    Raises:
        ValueError: If the backend is not supported.
    """
    if backend == "matplotlib":
        return MatplotlibBackend(space_drawer)
    if backend == "altair":
        return AltairBackend(space_drawer)
    raise ValueError(f"Unsupported backend: {backend}")


def map_coordinates(space, space_drawer, arguments):
    """Return a copy of the agent data with coordinates mapped to the space.

    Orthogonal grids, Voronoi grids, networks and continuous spaces use the
    coordinates directly; hex grids map them to hexagon centres.
    """
    mapped_arguments = arguments.copy()

    if isinstance(space, OrthogonalGrid | VoronoiGrid | ContinuousSpace | Network):
        mapped_arguments["loc"] = arguments["loc"].astype(float)

    elif isinstance(space, HexGrid):
        loc = arguments["loc"].astype(float)
        if loc.size > 0:
            # Calculate hexagon centers
            loc[:, 0] = loc[:, 0] * space_drawer.x_spacing + ((loc[:, 1] - 1) % 2) * (
                space_drawer.x_spacing / 2
            )
            loc[:, 1] = loc[:, 1] * space_drawer.y_spacing
        mapped_arguments["loc"] = loc

    return mapped_arguments
