# Coupling agents with fields and ODEs

`modelly.couple` joins agents to continuous processes: a pollutant, nutrient or heat field that
diffuses over a grid, an ODE, a system-dynamics stock-flow model. Each runs on its own time
scale inside the model's step, and a coupling schedule says who reads which quantity and who
writes it, checked before the first step. It needs only numpy and scipy, so it works the same
on Windows, macOS and Linux.

| Component | What it advances | How |
|---|---|---|
| `Field` | a grid property layer: diffusion, advection, decay | finite volumes, explicit sub-steps or backward Euler |
| `ODE` | named state variables, `dy/dt = rhs(t, y, inputs)` | `scipy.integrate.solve_ivp` |
| `StockFlow` | stocks joined by flows | `solve_ivp`, with every flow's running total |
| `Phase` | an agent step phase (any method) | calls it |
| `Coupling` | all of the above, once per step | phase by phase, writers before readers |

Two zoo models are built this way: [foragers on a nutrient field](zoo/nutrient_foragers.md)
and an [epidemic coupled to hospital capacity](zoo/hospital_epidemic.md).

## A worked example

Households heat their homes more when it is cold; the smoke drifts east, diffuses and decays;
the smoke on the grid warms a regional temperature, which the households read the next step.

```python
import numpy as np

from modelly.core.model import Model
from modelly.couple import ODE, Coupling, Field, Phase, Transport
from modelly.space.grid.grids import OrthogonalMooreGrid


def temperature(t, y, inputs):
    """Mean temperature relaxes towards a value raised by the smoke on the grid."""
    return (15.0 + 0.01 * inputs["smoke"].sum() - y) / 10.0


class Town(Model):
    def __init__(self, rng=42):
        super().__init__(rng=rng)
        self.grid = OrthogonalMooreGrid((30, 30), random=self.random)
        self.coupling = Coupling()
        self.coupling.add(Phase(self.emit, reads=["temperature"], writes=["emissions"]))
        smoke = Transport(diffusion=0.5, velocity=(0.2, 0.0), decay=0.05)
        self.smoke = self.coupling.add(
            Field(self.grid, "smoke", smoke, source="emissions"), phase=1
        )
        self.climate = self.coupling.add(
            ODE(temperature, {"temperature": 15.0}, reads=["smoke"]), phase=2
        )
        self.coupling.build()

    def emit(self):
        heating = max(0.0, 18.0 - self.coupling["temperature"])
        emissions = np.zeros((30, 30))
        emissions[10:20, 10:20] = heating * self.rng.random((10, 10))
        self.coupling["emissions"] = emissions

    def step(self):
        self.coupling.step()


town = Town()
town.run_for(50)
town.coupling.order  # ["Phase 'emit'", "Field 'smoke'", "ODE 'temperature'"]
town.climate.state  # {'temperature': 17.76...}
town.grid.smoke  # the field is the grid's property layer; cell.smoke reads it too
```

## The coupling schedule

Every component declares the quantities it `reads` and `writes`, by name; their values live in
the coupling (`coupling["temperature"]`). `coupling.add(component, phase=k)` schedules a
component, and `coupling.step(duration=1.0)` runs them all from `coupling.time` to
`coupling.time + duration`:

- phases run in increasing order;
- inside a phase a writer runs before its readers, otherwise in the order they were added;
- a component that reads a quantity written in a later phase reads the previous step's value.
  A feedback loop between agents and a continuous process is a loop across two phases, with a
  lag of one step.

`coupling.build()` (called by the first `step` if you do not call it) checks the declarations
and raises `CouplingError`, naming the components, for:

| Problem | Example message |
|---|---|
| a quantity read but never written | `Phase 'emit' reads 'temprature', which nobody writes. Did you mean 'temperature'?` |
| two writers of one quantity | `'emissions' has two writers: Phase 'emit' and Phase 'factories'.` |
| a cycle of reads and writes in one phase | `Phase 0 has a cycle of reads and writes between ...; put one of them in a later phase so it reads the previous step's values.` |
| a lagged read with no initial value | `... reads 'x' before ... writes it, and there is no initial value: give the writer one.` |

Fields and ODEs publish their initial state at build time; a `Phase` gives initial values for
lagged readers with `Phase(..., initial={"emissions": 0.0})`. During a step a component may only
set the quantities it declares: writing another one raises `CouplingError`.

A `Phase` calls its function with no arguments; use a method of the model (or a module-level
function, or a `functools.partial` of one) so the model can still be
[checkpointed](checkpoints.md).

## Fields

`Field(grid, name, transport, source=None)` makes the float property layer `name` of an
orthogonal grid (Moore or von Neumann, of any dimension), or adopts it if the grid already has
one, for example a [raster](geospatial.md) attached with `RasterLayer.attach`. It advances

```text
du/dt = D lap(u) - v . grad(u) - k u
```

with the coefficients of its `Transport`:

| Field | Default | Meaning |
|---|---|---|
| `diffusion` | `0.0` | `D`, in spacings squared per unit time |
| `velocity` | `()` | `v`, one component per grid axis |
| `decay` | `0.0` | `k`, per unit time |
| `boundary` | `None` | `"closed"` (no flux), `"absorbing"` (zero outside) or `"periodic"`; `None` is periodic on a torus, closed otherwise |
| `spacing` | `1.0` | the width of a cell |
| `dt` | `None` | the longest sub-step |
| `scheme` | `"explicit"` | `"explicit"` (forward Euler) or `"implicit"` (backward Euler) |

The scheme is a finite-volume one: central differences for diffusion and first-order upwind
for advection, written as fluxes through the faces between neighbouring cells, so each flux
leaves one cell and enters the next. The total is conserved to round-off with closed and
periodic boundaries; what leaves through an absorbing one is counted in `field.outflow`. Decay
is applied exactly, as `exp(-k dt)` per sub-step, and counted in `field.decayed`; with a
uniform `k` it commutes with the transport, so the splitting adds no error.

**Time stepping.** A step of length `duration` is cut into the fewest equal sub-steps no longer
than `dt`. The explicit scheme is positive and stable when

```text
dt * (2 * d * D / h**2 + sum(|v_i|) / h) <= 1
```

for a grid of `d` dimensions and spacing `h` (the diffusion limit `h**2 / (2 d D)` and the CFL
condition of upwind advection in one), and `Field` refuses a larger `dt` with a message that
names the limit. By default it takes half the limit. For stiff problems (fast diffusion, fine
grids) use `scheme="implicit"`: one sparse LU factorisation per sub-step length, stable and
positive for any `dt`, first order in time. The default implicit sub-step is the whole step.

**Sources.** Agents change a field through its `source` quantity: an amount per cell (an array
shaped like the grid, or a scalar), positive for emissions and negative for uptake, added at
the start of each step and counted in `field.added`. The budget then closes exactly:

```python
field.total() == initial + field.added - field.outflow - field.decayed  # to round-off
```

Agents read the field directly (`cell.smoke`, `grid.smoke`, `coupling["smoke"]`): the layer is
updated in place, so every view sees the new values. Do not assign the layer
(`grid.smoke = array` detaches it); write through the source quantity instead.

**Checked against known answers** in `tests/couple/test_field.py`: the second moment of a
spreading pulse grows by exactly `2 D t` per axis; a Gaussian follows the heat kernel within the
scheme's truncation error, which vanishes at `D dt / h**2 = 1/6`; upwind drift moves the centre
of mass by exactly `v t`; the total decays as `exp(-k t)`; closed and periodic boundaries
conserve mass to round-off and absorbing ones account for all of it; the stiff implicit field
settles on the exact discrete zero-flux profile.

## ODEs and stock-flow models

`ODE(rhs, initial, reads=(), solver=None)` holds the state variables named in `initial` and
integrates `dy/dt = rhs(t, y, inputs)`, `inputs` mapping each quantity it reads to its value at
the start of the step, held over the step. It writes its state variables, by name.

```python
from modelly.couple import ODE, Solver


def logistic(t, y, inputs):
    return 0.8 * y * (1 - y / 50.0)


ode = ODE(logistic, {"n": 1.0}, solver=Solver(method="LSODA", rtol=1e-9))
ode.advance(0.0, 5.0)
ode.state  # {'n': 26.35...}, the closed form 50 / (1 + 49 exp(-4))
```

`StockFlow(stocks, flows, reads=(), solver=None)` is the system-dynamics form. A
`Flow(name, rate, source=None, target=None)` moves material from its `source` stock to its
`target` stock (`None` is the outside) at `rate(stocks, inputs)` per unit time. It writes its
stocks, and keeps the amount each flow has moved in `totals`. Runge-Kutta methods keep linear
invariants exactly, so the stocks change by exactly the net flow across the boundary, to
round-off, whatever the tolerances:

```python
from modelly.couple import Flow, StockFlow


def admitted(stocks, inputs):
    return inputs["admissions"]


def discharged(stocks, inputs):
    return stocks["occupied"] / 8.0


hospital = StockFlow(
    {"occupied": 0.0},
    [
        Flow("admit", admitted, target="occupied"),
        Flow("discharge", discharged, source="occupied"),
    ],
    reads=["admissions"],
)
```

`Solver(method="RK45", rtol=1e-8, atol=1e-10)` passes its fields to `solve_ivp`: `"RK45"`
(Dormand-Prince) and `"DOP853"` for smooth problems, `"Radau"`, `"BDF"` or `"LSODA"` for stiff
ones. A failed integration raises `CouplingError` with scipy's message. Rate and right-hand-side
functions must be module-level functions, methods or partials of them, so the model can be
saved.

## Checkpoints and determinism

A coupled model saves and loads like any other (`model.save`, `Model.load`). The field's layer
is saved once, with the grid, and after a load the field, the grid, its cells and the coupling
share the same array again; implicit factorisations are rebuilt on the next step. Every
integration starts afresh from the stored state, so a run resumed from a checkpoint is the same
run, bit for bit, as one that never stopped (`tests/couple/test_schedule.py` and both zoo
models check it).

The coupling draws no random numbers, so the [determinism rules](determinism.md) are the
model's own. Two outputs pass through operations that are not correctly rounded and may differ
in the last bit between platforms, so compare them with a tolerance across machines: field
decay (`exp`) and the error norm `solve_ivp` uses to choose its steps. On one machine, and
between a straight and a resumed run, they are exact.

## Limits

- Fields live on orthogonal grids with uniform spacing and uniform coefficients; hexagonal
  grids, networks and continuous space have no field type yet.
- Advection is first-order upwind: it conserves mass and keeps values positive, and it smears
  sharp fronts (numerical diffusion of about `|v| h / 2`).
- ODE inputs are held over the step; to resolve a process faster than the agents' step, make
  the step shorter.
