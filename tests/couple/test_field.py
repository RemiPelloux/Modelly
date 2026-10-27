"""Fields against known answers: conservation, Gaussian spreading, drift, decay, outflow."""

from random import Random

import numpy as np
import pytest

from modelly.couple.field import Field, Transport
from modelly.couple.operator import stability_limit, transport_matrix
from modelly.couple.schedule import CouplingError
from modelly.space.grid.grids import (
    HexGrid,
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
)

SCHEMES = ("explicit", "implicit")
# Round-off on sums of a few thousand terms of order one.
ROUND_OFF = 1e-12
LINE = 201
CENTER = LINE // 2


def grid(shape, torus=False):
    """A seeded orthogonal grid."""
    return OrthogonalMooreGrid(shape, torus=torus, random=Random(1))


def moments(values, axis_values):
    """Mass, mean and variance of a 1-D profile."""
    mass = values.sum()
    mean = (axis_values * values).sum() / mass
    return mass, mean, ((axis_values - mean) ** 2 * values).sum() / mass


def random_field(transport, shape=(12, 9), torus=False, seed=3):
    """A field on a fresh grid with non-negative random values."""
    field = Field(grid(shape, torus), "u", transport)
    field.values[:] = np.random.default_rng(seed).random(shape)
    return field


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize(
    ("boundary", "torus"), [("closed", False), ("periodic", True), (None, True)]
)
def test_mass_is_conserved_to_round_off(scheme, boundary, torus):
    """No-flux and periodic boundaries keep the total, with diffusion and drift."""
    transport = Transport(
        diffusion=0.4, velocity=(0.3, -0.8), boundary=boundary, scheme=scheme, dt=0.2
    )
    field = random_field(transport, torus=torus)
    before = field.total()
    field.advance(25.0)
    assert field.total() == pytest.approx(before, rel=ROUND_OFF)
    assert field.outflow == 0.0
    assert (field.values >= 0).all()


@pytest.mark.parametrize("scheme", SCHEMES)
def test_variance_of_a_spreading_pulse_grows_by_2dt(scheme):
    """Away from the walls the discrete second moment grows by exactly ``2 D t``.

    Summing ``x**2`` against the discrete Laplacian gives ``2 D * mass`` per unit time, for
    forward and for backward Euler, so the identity holds to round-off.
    """
    diffusion, duration = 0.3, 40.0
    field = Field(
        grid((LINE,)), "u", Transport(diffusion=diffusion, scheme=scheme, dt=0.5)
    )
    field.values[CENTER] = 1.0
    field.advance(duration)
    mass, mean, variance = moments(field.values, np.arange(LINE))
    assert mass == pytest.approx(1.0, rel=ROUND_OFF)
    assert mean == pytest.approx(CENTER, rel=ROUND_OFF)
    assert variance == pytest.approx(2 * diffusion * duration, rel=1e-10)


@pytest.mark.parametrize(("dt", "bound"), [(0.1, 3e-4), (1.0 / 3.0, 2e-6)])
def test_gaussian_profile_matches_the_heat_kernel(dt, bound):
    """A Gaussian of variance ``s0`` becomes the Gaussian of variance ``s0 + 2 D t``.

    The leading truncation error of forward Euler with central differences is
    ``(D h**2 / 12 - D**2 dt / 2) u_xxxx``: about 0.2 % of the peak (0.07) for ``dt = 0.1``,
    and zero for ``D dt / h**2 = 1/6``, where the scheme is fourth order (Morton and
    Mayers, 2005, section 2.6).
    """
    diffusion, duration, s0 = 0.5, 20.0, 9.0
    x = np.arange(LINE) - CENTER
    field = Field(grid((LINE,)), "u", Transport(diffusion=diffusion, dt=dt))
    field.values[:] = np.exp(-(x**2) / (2 * s0)) / np.sqrt(2 * np.pi * s0)
    field.advance(duration)
    s = s0 + 2 * diffusion * duration
    exact = np.exp(-(x**2) / (2 * s)) / np.sqrt(2 * np.pi * s)
    assert np.max(np.abs(field.values - exact)) < bound


def test_two_dimensional_spreading_is_isotropic():
    """In 2-D each axis gets ``2 D t`` of variance, on a von Neumann grid too."""
    size, diffusion, duration = 61, 0.2, 15.0
    space = OrthogonalVonNeumannGrid((size, size), random=Random(2))
    field = Field(space, "u", Transport(diffusion=diffusion))
    field.values[size // 2, size // 2] = 1.0
    field.advance(duration)
    axis = np.arange(size)
    for profile in (field.values.sum(axis=1), field.values.sum(axis=0)):
        _, _, variance = moments(profile, axis)
        assert variance == pytest.approx(2 * diffusion * duration, rel=1e-10)


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("speed", [0.7, -0.4])
def test_upwind_drift_moves_the_centre_of_mass_at_the_velocity(scheme, speed):
    """Upwind advection moves the mean by exactly ``v t`` and spreads it numerically."""
    duration = 30.0
    field = Field(
        grid((LINE,)), "u", Transport(velocity=(speed,), scheme=scheme, dt=1.0)
    )
    field.values[CENTER] = 1.0
    field.advance(duration)
    mass, mean, _ = moments(field.values, np.arange(LINE))
    assert mass == pytest.approx(1.0, rel=ROUND_OFF)
    assert mean == pytest.approx(CENTER + speed * duration, rel=ROUND_OFF)


def test_periodic_drift_wraps_around():
    """On a ring a drifting pulse comes back; nothing is lost."""
    field = Field(grid((10,), torus=True), "u", Transport(velocity=(1.0,), dt=1.0))
    field.values[0] = 1.0
    field.advance(10.0)  # Courant number 1: the pulse moves one cell per step
    assert field.values[0] == pytest.approx(1.0)
    assert field.total() == pytest.approx(1.0, rel=ROUND_OFF)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_decay_is_exponential_and_accounted(scheme):
    """The total decays as ``exp(-k t)``, and ``decayed`` is the difference."""
    decay, duration = 0.15, 12.0
    field = random_field(Transport(diffusion=0.3, decay=decay, scheme=scheme, dt=0.3))
    before = field.total()
    field.advance(duration)
    assert field.total() == pytest.approx(
        before * np.exp(-decay * duration), rel=ROUND_OFF
    )
    assert field.total() + field.decayed == pytest.approx(before, rel=ROUND_OFF)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_absorbing_boundary_counts_what_leaves(scheme):
    """``total + outflow`` stays the initial mass, and the domain empties out."""
    transport = Transport(
        diffusion=0.5, velocity=(0.2, 0.0), boundary="absorbing", scheme=scheme, dt=0.4
    )
    field = random_field(transport, shape=(10, 10))
    before = field.total()
    field.advance(5.0)
    assert 0 < field.outflow < before
    assert field.total() + field.outflow == pytest.approx(before, rel=ROUND_OFF)
    field.advance(2000.0)
    assert field.total() < 1e-6 * before


def test_budget_with_sources():
    """``total = start + added - outflow - decayed``, whatever happens in between."""
    transport = Transport(diffusion=0.25, decay=0.05, boundary="absorbing", dt=0.5)
    field = random_field(transport, shape=(8, 8))
    start = field.total()
    supply = np.zeros((8, 8))
    supply[0, :] = 2.0
    for _ in range(30):
        field.add(supply)
        field.add(-0.5 * field.values)  # uptake of half the field
        field.advance(1.0)
    balance = start + field.added - field.outflow - field.decayed
    assert field.total() == pytest.approx(balance, rel=ROUND_OFF)


def test_explicit_scheme_refuses_an_unstable_step():
    """Above ``h**2 / (2 d D)`` the explicit scheme raises and points to the implicit one."""
    limit = 1.0 / (2 * 2 * 0.5)  # 2-D, D = 0.5, spacing 1
    Field(grid((5, 5)), "ok", Transport(diffusion=0.5, dt=limit))
    with pytest.raises(CouplingError, match="implicit"):
        Field(grid((5, 5)), "u", Transport(diffusion=0.5, dt=1.01 * limit))
    with pytest.raises(CouplingError, match="positive"):
        Field(grid((5, 5)), "u", Transport(diffusion=0.5, dt=0.0))


def test_stability_limit_combines_diffusion_and_cfl():
    """The limit is ``1 / (2 d D / h**2 + sum |v| / h)``."""
    matrix, _ = transport_matrix((6, 6), (0.5, (1.0, -2.0), 2.0), "periodic")
    assert stability_limit(matrix) == pytest.approx(1.0 / (4 * 0.5 / 4.0 + 3.0 / 2.0))
    still, _ = transport_matrix((3,), (0.0, (0.0,), 1.0), "closed")
    assert stability_limit(still) == np.inf


def test_explicit_at_the_limit_and_implicit_with_a_huge_step_stay_positive():
    """Both schemes keep a non-negative field non-negative and conserve it.

    The stiff implicit system has entries ``dt * D`` of order 1e4, so its LU solve
    conserves the total to about ``1e4 * eps`` per step rather than ``eps``.
    """
    explicit = Transport(diffusion=2.0, velocity=(1.0, 1.0), dt=1.0 / 10.0)  # the limit
    stiff = Transport(diffusion=50.0, velocity=(3.0, 1.0), scheme="implicit", dt=100.0)
    for transport, rel in ((explicit, ROUND_OFF), (stiff, 1e-10)):
        field = random_field(transport)
        before = field.total()
        field.advance(300.0)
        assert (field.values >= 0).all()
        assert field.total() == pytest.approx(before, rel=rel)
    # Behind closed walls the stiff field settles where every face flux is zero:
    # (D + v) u[p] = D u[q], a geometric profile of ratio 1 + v / D along each axis.
    assert np.allclose(field.values[1:] / field.values[:-1], 1 + 3.0 / 50.0, rtol=1e-9)
    assert np.allclose(
        field.values[:, 1:] / field.values[:, :-1], 1 + 1.0 / 50.0, rtol=1e-9
    )


def test_sub_steps_divide_the_step_evenly():
    """The step is cut into the fewest equal sub-steps no longer than ``dt``."""
    field = Field(grid((5,)), "u", Transport(diffusion=1.0))
    assert field.dt == pytest.approx(0.25)  # half of the limit 1 / (2 D)
    implicit = Field(grid((5,)), "v", Transport(diffusion=1.0, scheme="implicit"))
    assert implicit.dt == np.inf
    implicit.values[0] = 1.0
    implicit.advance(3.0)
    assert len(implicit._solvers) == 1
    implicit.advance(0.0)  # a zero step does nothing
    assert implicit.total() == pytest.approx(1.0)


def test_layer_is_shared_with_the_grid_and_its_cells():
    """``cell.<name>`` and ``grid.<name>`` read the field's array as it changes."""
    space = grid((7, 7))
    field = Field(space, "heat", Transport(diffusion=0.5))
    assert field.values is space.heat is space.property_layers["heat"]
    field.values[3, 3] = 1.0
    field.advance(1.0)
    cell = space._cells[(3, 4)]
    assert cell.heat == field.values[3, 4] > 0


def test_adopts_an_existing_layer():
    """A layer created beforehand (a raster, say) keeps its values."""
    space = grid((4, 4))
    space.create_property_layer("water", 2.0)
    field = Field(space, "water")
    assert field.total() == 32.0
    space.create_property_layer("count", 0, dtype=int)
    with pytest.raises(CouplingError, match="float"):
        Field(space, "count")


@pytest.mark.parametrize(
    ("transport", "message"),
    [
        (Transport(boundary="sticky"), "boundary"),
        (Transport(scheme="magic"), "scheme"),
        (Transport(velocity=(1.0,)), "axes"),
        (Transport(diffusion=-1.0), "non-negative"),
        (Transport(spacing=0.0), "spacing"),
    ],
)
def test_bad_parameters_are_refused(transport, message):
    """Unknown boundary or scheme, a wrong velocity, a negative coefficient."""
    with pytest.raises(CouplingError, match=message):
        Field(grid((3, 3)), "u", transport)


def test_hex_grids_are_refused():
    """A hexagonal grid has no Cartesian stencil."""
    with pytest.raises(CouplingError, match="orthogonal"):
        Field(HexGrid((4, 4), random=Random(1)), "u")
