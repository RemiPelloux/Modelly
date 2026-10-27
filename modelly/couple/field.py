"""Fields: a grid property layer that diffuses, drifts and decays on its own time step.

A ``Field`` owns one property layer of an orthogonal grid (``grid.<name>``, and
``cell.<name>`` on every cell) and advances it by

    du/dt = D lap(u) - v . grad(u) - k u

with the transport operator of ``modelly.couple.operator``: finite volumes, central
diffusion and upwind advection, so the total is conserved to round-off with closed or
periodic boundaries and what leaves through an absorbing one is counted in ``outflow``.
The decay ``-k u`` is applied exactly, as ``exp(-k dt)`` per sub-step; with a uniform ``k``
it commutes with transport, so splitting it off adds no error.

A step of length ``duration`` is cut into equal sub-steps no longer than ``dt``. The
explicit scheme (the default) needs ``dt`` within the stability limit and refuses a larger
one; by default it takes half of the limit. The implicit scheme (backward Euler, one sparse
LU factorisation per sub-step length) is stable for any ``dt``, for stiff diffusion.

The layer is updated in place, so agents reading ``cell.<name>`` and vectorised code
reading ``grid.<name>`` see the new values, and a checkpoint saves it once with the grid.
Agents change the field through its ``source`` quantity (an amount per cell, negative for
uptake, added at the start of each step), so the budget ``added - outflow - decayed`` keeps
track of every change of ``total()``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.couple.operator import (
    BOUNDARIES,
    CLOSED,
    PERIODIC,
    stability_limit,
    transport_matrix,
)
from modelly.couple.schedule import CouplingError
from modelly.space.grid.grids import HexGrid

if TYPE_CHECKING:
    from modelly.couple.schedule import Coupling
    from modelly.space.grid.base import Grid

EXPLICIT, IMPLICIT = "explicit", "implicit"
# The default explicit sub-step, as a share of the stability limit.
DEFAULT_SAFETY = 0.5


@dataclass(frozen=True)
class Transport:
    """What a field does between two steps.

    Attributes:
        diffusion: the diffusion coefficient ``D``, in cell spacings squared per unit time
            when ``spacing`` is 1.
        velocity: the advection velocity, one component per grid axis (empty: none).
        decay: the first-order decay rate ``k`` per unit time.
        boundary: ``"closed"`` (no flux), ``"absorbing"`` (zero outside, mass leaves) or
            ``"periodic"``; ``None`` means periodic on a torus and closed otherwise.
        spacing: the width of a cell, in the units of ``D`` and ``velocity``.
        dt: the longest sub-step; ``None`` takes half the explicit stability limit, or one
            sub-step per step with the implicit scheme.
        scheme: ``"explicit"`` (forward Euler) or ``"implicit"`` (backward Euler).
    """

    diffusion: float = 0.0
    velocity: tuple[float, ...] = ()
    decay: float = 0.0
    boundary: str | None = None
    spacing: float = 1.0
    dt: float | None = None
    scheme: str = EXPLICIT


class Field:
    """A grid property layer with a transport solver, a coupling component.

    Attributes:
        values: the layer, shaped like the grid (the same array as ``grid.<name>``).
        added: total amount added through ``add`` (or the ``source`` quantity).
        outflow: total amount that left through absorbing boundaries.
        decayed: total amount removed by decay.

    Example:
        >>> from random import Random
        >>> from modelly.space.grid.grids import OrthogonalMooreGrid
        >>> grid = OrthogonalMooreGrid((20, 20), random=Random(1))
        >>> heat = Field(grid, "heat", Transport(diffusion=0.5))
        >>> heat.values[10, 10] = 1.0
        >>> heat.advance(5.0)
        >>> round(heat.total(), 12)
        1.0
    """

    def __init__(
        self,
        grid: Grid,
        name: str,
        transport: Transport | None = None,
        source: str | None = None,
    ) -> None:
        """Make (or adopt, if ``grid`` already has it) the float layer ``name`` of ``grid``.

        Args:
            grid: an orthogonal grid (Moore or von Neumann), of any dimension.
            name: the property layer, also the quantity the field writes in a coupling.
            transport: the coefficients, boundary and time stepping (none by default).
            source: a quantity read every step and added to the layer before transport.
        """
        transport = transport or Transport()
        self.name = name
        self.label = f"Field {name!r}"
        self.transport = transport
        self.values = _layer(grid, name)
        self.boundary = transport.boundary or (PERIODIC if grid.torus else CLOSED)
        _check(transport, self.boundary, self.values.ndim)
        velocity = transport.velocity or (0.0,) * self.values.ndim
        coefficients = (transport.diffusion, tuple(velocity), transport.spacing)
        self.matrix, self.leak = transport_matrix(
            self.values.shape, coefficients, self.boundary
        )
        self.dt = self._time_step()
        self.reads = () if source is None else (source,)
        self.writes = (name,)
        self.added = self.outflow = self.decayed = 0.0
        self._solvers: dict[float, Any] = {}

    def _time_step(self) -> float:
        """The longest sub-step: the given one, checked, or the default."""
        t = self.transport
        limit = stability_limit(self.matrix)
        if t.dt is None:
            return math.inf if t.scheme == IMPLICIT else DEFAULT_SAFETY * limit
        if t.dt <= 0:
            raise CouplingError(f"{self.label}: dt must be positive, got {t.dt}.")
        if t.scheme == EXPLICIT and t.dt > limit:
            raise CouplingError(
                f"{self.label}: dt={t.dt} exceeds the explicit stability limit {limit:.6g} "
                "(diffusion and advection CFL condition); use a smaller dt or scheme='implicit'."
            )
        return t.dt

    def total(self) -> float:
        """The sum of the layer: the amount in the domain."""
        return float(self.values.sum())

    def add(self, amounts: Any) -> None:
        """Add ``amounts`` (a scalar or an array shaped like the grid) to the layer."""
        before = self.total()
        self.values += amounts
        self.added += self.total() - before

    def advance(self, duration: float) -> None:
        """Transport and decay for ``duration``, in equal sub-steps of at most ``dt``."""
        if duration <= 0:
            return
        steps = 1 if math.isinf(self.dt) else max(1, math.ceil(duration / self.dt))
        h = duration / steps
        flat = self.values.reshape(-1)
        keep = math.exp(-self.transport.decay * h)
        for _ in range(steps):
            if self.transport.scheme == IMPLICIT:
                flat[:] = self._solver(h)(flat)
                self.outflow += h * float(self.leak @ flat)
            else:
                self.outflow += h * float(self.leak @ flat)
                flat += h * (self.matrix @ flat)
            if keep != 1.0:
                self.decayed += (1.0 - keep) * float(flat.sum())
                flat *= keep

    def _solver(self, h: float):
        """The LU solve of ``(I - h A) x = b``, factorised once per sub-step length."""
        solve = self._solvers.get(h)
        if solve is None:
            from scipy.sparse import identity  # noqa: PLC0415 - scipy is heavy
            from scipy.sparse.linalg import factorized  # noqa: PLC0415

            system = (
                identity(self.matrix.shape[0], format="csc") - h * self.matrix.tocsc()
            )
            solve = self._solvers[h] = factorized(system)
        return solve

    def start(self, coupling: Coupling) -> None:
        """Publish the layer as the quantity ``name``."""
        coupling.values[self.name] = self.values

    def run(self, coupling: Coupling, time: float, duration: float) -> None:
        """Add the source quantity, if any, then advance."""
        if self.reads:
            self.add(coupling[self.reads[0]])
        self.advance(duration)

    def __getstate__(self) -> dict[str, Any]:
        """Drop the LU factorisations, which do not pickle; they are rebuilt on use."""
        return {k: v for k, v in self.__dict__.items() if k != "_solvers"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore the state with no factorisation cached."""
        self.__dict__.update(state)
        self._solvers = {}


def _layer(grid: Grid, name: str) -> np.ndarray:
    """The grid's layer ``name``, created at 0.0 when missing; it must be a float array."""
    if isinstance(grid, HexGrid):
        raise CouplingError(
            "A Field needs an orthogonal grid; a HexGrid has no Cartesian stencil."
        )
    if name not in grid.property_layers:
        return grid.create_property_layer(name, 0.0, dtype=float)
    values = grid.property_layers[name]
    if not np.issubdtype(values.dtype, np.floating) or not values.flags.c_contiguous:
        raise CouplingError(
            f"Layer {name!r} must be a C-contiguous float array to be a Field."
        )
    return values


def _check(transport: Transport, boundary: str, ndim: int) -> None:
    """Reject an unknown boundary or scheme, a wrong velocity or a negative coefficient."""
    if boundary not in BOUNDARIES:
        raise CouplingError(f"Unknown boundary {boundary!r}; use one of {BOUNDARIES}.")
    if transport.scheme not in (EXPLICIT, IMPLICIT):
        raise CouplingError(
            f"Unknown scheme {transport.scheme!r}; use 'explicit' or 'implicit'."
        )
    if transport.velocity and len(transport.velocity) != ndim:
        raise CouplingError(
            f"velocity has {len(transport.velocity)} components; the grid has {ndim} axes."
        )
    if min(transport.diffusion, transport.decay) < 0 or transport.spacing <= 0:
        raise CouplingError(
            "diffusion and decay must be non-negative and spacing positive."
        )
