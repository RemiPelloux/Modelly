"""Agents located at a point of a ``GeoSpace``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import shapely

from modelly.space.continuous.agents import ContinuousSpaceAgent

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.space.geo.space import GeoSpace


class GeoAgent(ContinuousSpaceAgent):
    """An agent at a point of a ``GeoSpace``; its position is a row of the position array.

    Attributes:
        space (GeoSpace): the space the agent is in.
        position (np.ndarray): ``(x, y)`` in the space's CRS.
    """

    def __init__(
        self, space: GeoSpace, model: Model, position: Any = None, crs: Any = None
    ) -> None:
        """Place a new agent in ``space``.

        Args:
            space: the geospatial space.
            model: the model the agent belongs to.
            position: a Shapely ``Point`` or ``(x, y)``; defaults to the centre of the space.
            crs: the CRS of ``position``, if not the space's.
        """
        super().__init__(space, model)
        self.move_to(space.center if position is None else position, crs)

    def move_to(self, point: Any, crs: Any = None) -> None:
        """Move to ``point`` (a Shapely ``Point`` or ``(x, y)``, in ``crs``)."""
        self.space.move_to(self, point, crs)

    @property
    def region(self) -> Any:
        """The label of the region the agent is in, or ``None``."""
        return self.space.region_of(self.position)

    @property
    def geometry(self) -> shapely.Point:
        """The agent's position as a Shapely ``Point``."""
        return shapely.Point(self.position)
