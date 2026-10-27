"""The transport operator of a field: diffusion and upwind advection as one sparse matrix.

A field ``u`` on a regular grid of spacing ``h`` obeys ``du/dt = D lap(u) - v . grad(u)``
(decay is applied separately, exactly). The finite-volume semi-discretisation writes it as
fluxes through the faces between neighbouring cells: through the face from cell ``p`` to the
next cell ``q`` along an axis, with speed ``v`` along that axis, the flux is

    F = (D / h**2 + max(v, 0) / h) * u[p] - (D / h**2 + max(-v, 0) / h) * u[q]

(central differences for diffusion, first-order upwind for advection). Each flux leaves one
cell and enters the other, so the total is conserved: every column of the matrix ``A`` in
``du/dt = A u`` sums to zero, except at an absorbing boundary, where the flux through the
outer face leaves the domain (``leak``, with the outside held at zero). A periodic boundary
adds the face between the last and the first cell. A closed one has no outer face (no flux).

The off-diagonal entries of ``A`` are non-negative, so explicit Euler with a step ``dt`` at
most ``1 / max(-diag(A))`` keeps every new value a non-negative combination of the old ones:
positive, stable and conservative (the CFL condition of upwind advection and the classical
``dt <= h**2 / (2 d D)`` of diffusion are both special cases). Backward Euler,
``(I - dt A) u_new = u_old``, keeps these properties for any ``dt``.

References:
    LeVeque, R. J. (2002). Finite Volume Methods for Hyperbolic Problems. Cambridge
    University Press.

    Hundsdorfer, W. and Verwer, J. G. (2003). Numerical Solution of Time-Dependent
    Advection-Diffusion-Reaction Equations. Springer.
"""

from __future__ import annotations

from math import prod
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix

CLOSED, ABSORBING, PERIODIC = "closed", "absorbing", "periodic"
BOUNDARIES = (CLOSED, ABSORBING, PERIODIC)


def transport_matrix(
    shape: tuple[int, ...],
    coefficients: tuple[float, tuple[float, ...], float],
    boundary: str,
) -> tuple[csr_matrix, np.ndarray]:
    """``(A, leak)`` for cells in C order: ``du/dt = A u``, and ``leak @ u`` leaves per unit time.

    Args:
        shape: the grid's dimensions.
        coefficients: ``(diffusion, velocity per axis, spacing)``.
        boundary: ``"closed"``, ``"absorbing"`` or ``"periodic"``.
    """
    from scipy.sparse import coo_matrix  # noqa: PLC0415 - scipy is heavy

    diffusion, velocity, spacing = coefficients
    n = prod(shape)
    index = np.arange(n).reshape(shape)
    entries = []
    leak = np.zeros(n)
    for axis, speed in enumerate(velocity):
        forward = diffusion / spacing**2 + max(speed, 0.0) / spacing
        backward = diffusion / spacing**2 + max(-speed, 0.0) / spacing
        lower, upper = _faces(index, axis, boundary == PERIODIC)
        entries += _face_entries(lower, upper, forward, backward)
        if boundary == ABSORBING:
            leak[np.take(index, -1, axis=axis).ravel()] += forward
            leak[np.take(index, 0, axis=axis).ravel()] += backward
    entries.append((index.ravel(), index.ravel(), -leak))
    rows, cols, data = (np.concatenate(part) for part in zip(*entries))
    return coo_matrix((data, (rows, cols)), shape=(n, n)).tocsr(), leak


def _face_entries(
    lower: np.ndarray, upper: np.ndarray, forward: float, backward: float
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """``(rows, columns, values)`` of the flux ``forward * u[lower] - backward * u[upper]``.

    The flux leaves ``lower`` and enters ``upper``, one entry pair per face.
    """
    pairs = ((lower, lower, -forward), (lower, upper, backward))
    pairs += ((upper, lower, forward), (upper, upper, -backward))
    return [(row, col, np.full(lower.size, value)) for row, col, value in pairs]


def _faces(
    index: np.ndarray, axis: int, periodic: bool
) -> tuple[np.ndarray, np.ndarray]:
    """The cells on the lower and the upper side of every inner face along ``axis``."""
    if periodic:
        return index.ravel(), np.roll(index, -1, axis=axis).ravel()
    size = index.shape[axis]
    lower = np.take(index, np.arange(size - 1), axis=axis)
    upper = np.take(index, np.arange(1, size), axis=axis)
    return lower.ravel(), upper.ravel()


def stability_limit(matrix: csr_matrix) -> float:
    """The largest explicit Euler step that keeps the scheme positive (``inf`` if none)."""
    rate = float(np.max(-matrix.diagonal(), initial=0.0))
    return np.inf if rate == 0.0 else 1.0 / rate
