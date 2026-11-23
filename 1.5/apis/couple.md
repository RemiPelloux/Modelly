# Coupling

`modelly.couple` couples agents to fields, ODEs and stock-flow models. How to use it is in [Coupling agents with fields and ODEs](https://remipelloux.github.io/Modelly/coupling.html).

## Schedule

The coupling schedule: who reads which quantity, who writes it, and in what order.

A `Coupling` runs components (fields, ODEs, stock-flow models and agent phases) once per step. Each component declares the quantities it `reads` and `writes`; the values live in the coupling, by name (`coupling["occupied"]`). Components run phase by phase, phase 0 first; within a phase a writer runs before its readers. A component that reads a quantity written in a later phase sees the value of the previous step, so feedback between agents and a continuous process is a loop across two phases.

`build` checks the declarations before the first step and raises `CouplingError` for a quantity read but never written, a quantity with two writers, a cycle of reads and writes inside one phase (no order would be right), and a quantity read before its writer has run with no initial value to read.

#### `exception CouplingError`

An inconsistent coupling schedule, or a continuous component that cannot step.

#### `class Component(*args, **kwargs)`

What a coupling runs: a label, declared reads and writes, `start` and `run`.

#### `start(coupling: Coupling) → None`

Publish the initial value of every quantity this component writes, if it has one.

#### `run(coupling: Coupling, time: float, duration: float) → None`

Advance from `time` to `time + duration`, reading and writing `coupling`.

#### `class Phase(function: Callable[[], Any], reads: Iterable[str] = (), writes: Iterable[str] = (), initial: dict[str, Any] | None = None)`

An agent step phase (or any callable) as a coupling component.

**Variables:**

- **function** – called with no arguments on every step, typically a model method.
- **reads** – the quantities it reads.
- **writes** – the quantities it writes.
- **initial** – initial values of some of its writes, for readers that run before it.

Wrap `function`; use a method or a module-level function so it can be saved.

#### `start(coupling: Coupling) → None`

Publish the initial values not yet set, so a rebuild keeps the current ones.

#### `run(coupling: Coupling, time: float, duration: float) → None`

Call the function.

#### `class Coupling`

A schedule of components, checked at build time and run once per step.

**Variables:**

- **values** – the current value of every quantity, by name.
- **time** – the coupling’s time, advanced by `step`.

Example

```default
>>> def emit():
...     coupling["load"] = 2.0
>>> def absorb(t, y, inputs):
...     return inputs["load"] - y
>>> from modelly.couple.ode import ODE
>>> coupling = Coupling()
>>> phase = coupling.add(Phase(emit, writes=["load"]))
>>> tank = coupling.add(ODE(absorb, {"level": 0.0}, reads=["load"]), phase=1)
>>> coupling.build().order
["Phase 'emit'", "ODE 'absorb'"]
>>> coupling.step()
>>> round(coupling["level"], 6)
1.264241
```

An empty schedule at time 0.

#### `add(component: C, phase: int = 0) → C`

Schedule `component` in `phase` (lower phases run first) and return it.

#### `property order: list[str]`

The labels of the components in the order they run (after `build`).

#### `build() → Coupling`

Check the declarations, order the components and publish initial values.

**Raises:**

[**CouplingError**](https://remipelloux.github.io/Modelly/apis/couple.html#modelly.couple.schedule.CouplingError) – a read with no writer, two writers of one quantity, a cycle in one phase, or a read before the first write with no initial value.

#### `step(duration: float = 1.0) → None`

Run every component once, from `time` to `time + duration`.

## Fields

Fields: a grid property layer that diffuses, drifts and decays on its own time step.

A `Field` owns one property layer of an orthogonal grid (`grid.<name>`, and `cell.<name>` on every cell) and advances it by

du/dt = D lap(u) - v . grad(u) - k u

with the transport operator of `modelly.couple.operator`: finite volumes, central diffusion and upwind advection, so the total is conserved to round-off with closed or periodic boundaries and what leaves through an absorbing one is counted in `outflow`. The decay `-k u` is applied exactly, as `exp(-k dt)` per sub-step; with a uniform `k` it commutes with transport, so splitting it off adds no error.

A step of length `duration` is cut into equal sub-steps no longer than `dt`. The explicit scheme (the default) needs `dt` within the stability limit and refuses a larger one; by default it takes half of the limit. The implicit scheme (backward Euler, one sparse LU factorisation per sub-step length) is stable for any `dt`, for stiff diffusion.

The layer is updated in place, so agents reading `cell.<name>` and vectorised code reading `grid.<name>` see the new values, and a checkpoint saves it once with the grid. Agents change the field through its `source` quantity (an amount per cell, negative for uptake, added at the start of each step), so the budget `added - outflow - decayed` keeps track of every change of `total()`.

#### `class Transport(diffusion: float = 0.0, velocity: tuple[float, ...] = (), decay: float = 0.0, boundary: str | None = None, spacing: float = 1.0, dt: float | None = None, scheme: str = 'explicit')`

What a field does between two steps.

**Variables:**

- **diffusion** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the diffusion coefficient `D`, in cell spacings squared per unit time when `spacing` is 1.
- **velocity** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*float*](https://docs.python.org/3/builtins/functions.html#float)*, **...**]*) – the advection velocity, one component per grid axis (empty: none).
- **decay** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the first-order decay rate `k` per unit time.
- **boundary** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – `"closed"` (no flux), `"absorbing"` (zero outside, mass leaves) or `"periodic"`; `None` means periodic on a torus and closed otherwise.
- **spacing** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the width of a cell, in the units of `D` and `velocity`.
- **dt** ([*float*](https://docs.python.org/3/builtins/functions.html#float)* | **None*) – the longest sub-step; `None` takes half the explicit stability limit, or one sub-step per step with the implicit scheme.
- **scheme** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"explicit"` (forward Euler) or `"implicit"` (backward Euler).

#### `class Field(grid: Grid, name: str, transport: Transport | None = None, source: str | None = None)`

A grid property layer with a transport solver, a coupling component.

**Variables:**

- **values** – the layer, shaped like the grid (the same array as `grid.<name>`).
- **added** – total amount added through `add` (or the `source` quantity).
- **outflow** – total amount that left through absorbing boundaries.
- **decayed** – total amount removed by decay.

Example

```default
>>> from random import Random
>>> from modelly.space.grid.grids import OrthogonalMooreGrid
>>> grid = OrthogonalMooreGrid((20, 20), random=Random(1))
>>> heat = Field(grid, "heat", Transport(diffusion=0.5))
>>> heat.values[10, 10] = 1.0
>>> heat.advance(5.0)
>>> round(heat.total(), 12)
1.0
```

Make (or adopt, if `grid` already has it) the float layer `name` of `grid`.

**Parameters:**

- **grid** – an orthogonal grid (Moore or von Neumann), of any dimension.
- **name** – the property layer, also the quantity the field writes in a coupling.
- **transport** – the coefficients, boundary and time stepping (none by default).
- **source** – a quantity read every step and added to the layer before transport.

#### `total() → float`

The sum of the layer: the amount in the domain.

#### `add(amounts: Any) → None`

Add `amounts` (a scalar or an array shaped like the grid) to the layer.

#### `advance(duration: float) → None`

Transport and decay for `duration`, in equal sub-steps of at most `dt`.

#### `start(coupling: Coupling) → None`

Publish the layer as the quantity `name`.

#### `run(coupling: Coupling, time: float, duration: float) → None`

Add the source quantity, if any, then advance.

The transport operator of a field: diffusion and upwind advection as one sparse matrix.

A field `u` on a regular grid of spacing `h` obeys `du/dt = D lap(u) - v . grad(u)` (decay is applied separately, exactly). The finite-volume semi-discretisation writes it as fluxes through the faces between neighbouring cells: through the face from cell `p` to the next cell `q` along an axis, with speed `v` along that axis, the flux is

F = (D / h**2 + max(v, 0) / h) * u[p] - (D / h**2 + max(-v, 0) / h) * u[q]

(central differences for diffusion, first-order upwind for advection). Each flux leaves one cell and enters the other, so the total is conserved: every column of the matrix `A` in `du/dt = A u` sums to zero, except at an absorbing boundary, where the flux through the outer face leaves the domain (`leak`, with the outside held at zero). A periodic boundary adds the face between the last and the first cell. A closed one has no outer face (no flux).

The off-diagonal entries of `A` are non-negative, so explicit Euler with a step `dt` at most `1 / max(-diag(A))` keeps every new value a non-negative combination of the old ones: positive, stable and conservative (the CFL condition of upwind advection and the classical `dt <= h**2 / (2 d D)` of diffusion are both special cases). Backward Euler, `(I - dt A) u_new = u_old`, keeps these properties for any `dt`.

References

LeVeque, R. J. (2002). Finite Volume Methods for Hyperbolic Problems. Cambridge University Press.

Hundsdorfer, W. and Verwer, J. G. (2003). Numerical Solution of Time-Dependent Advection-Diffusion-Reaction Equations. Springer.

#### `transport_matrix(shape: tuple[int, ...], coefficients: tuple[float, tuple[float, ...], float], boundary: str) → tuple[csr_matrix, np.ndarray]`

`(A, leak)` for cells in C order: `du/dt = A u`, and `leak @ u` leaves per unit time.

**Parameters:**

- **shape** – the grid’s dimensions.
- **coefficients** – `(diffusion, velocity per axis, spacing)`.
- **boundary** – `"closed"`, `"absorbing"` or `"periodic"`.

#### `stability_limit(matrix: csr_matrix) → float`

The largest explicit Euler step that keeps the scheme positive (`inf` if none).

## ODEs and stock-flow models

ODE and stock-flow components, integrated with `scipy.integrate.solve_ivp`.

An `ODE` holds named state variables `y` and a right-hand side `rhs(t, y, inputs)`, where `inputs` maps each quantity the component reads to its value at the start of the step; inputs are held constant over the step (a zero-order hold), as an agent phase produces them once per step. Every step integrates from `time` to `time + duration` with the adaptive Runge-Kutta (or implicit) method and tolerances of its `Solver`, then publishes each state variable under its name. The integration starts afresh every step from the stored state, so a run is a deterministic function of the state and the inputs, and a checkpointed model resumes bit for bit.

A `StockFlow` is the system-dynamics form: stocks, and flows that move material from one stock to another or across the model boundary (`None`), at a rate computed from the stocks and the inputs. Its equations are `d stock / dt = inflows - outflows`, and it also integrates the amount moved by each flow (`totals`). Runge-Kutta methods keep linear invariants exactly, so `sum(stocks) - sum(stocks at start)` equals the net amount moved in across the boundary to round-off: a mass balance that holds whatever the tolerances.

References

Dormand, J. R. and Prince, P. J. (1980). A family of embedded Runge-Kutta formulae. Journal of Computational and Applied Mathematics, 6(1), 19-26.

Sterman, J. D. (2000). Business Dynamics: Systems Thinking and Modeling for a Complex World. Irwin/McGraw-Hill.

#### `class Solver(method: str = 'RK45', rtol: float = 1e-08, atol: float = 1e-10)`

How `solve_ivp` integrates a step.

**Variables:**

- **method** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – a `solve_ivp` method: `"RK45"` (Dormand-Prince), `"DOP853"`, `"Radau"`, `"BDF"` or `"LSODA"` for stiff systems.
- **rtol** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the relative tolerance.
- **atol** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the absolute tolerance.

#### `class ODE(rhs: Callable[[float, ndarray, dict[str, Any]], Any], initial: dict[str, float], reads: Iterable[str] = (), solver: Solver | None = None)`

Named state variables advanced by `dy/dt = rhs(t, y, inputs)`, a coupling component.

**Variables:**

- **y** – the state, in the order of the `initial` mapping.
- **names** – the state variables, also the quantities the component writes.

Example

```default
>>> def decay(t, y, inputs):
...     return -0.5 * y
>>> ode = ODE(decay, {"amount": 1.0})
>>> ode.advance(0.0, 2.0)
>>> round(ode.state["amount"], 6)
0.367879
```

Start at `initial`; `rhs` must be a module-level function or a method to be saved.

#### `property state: dict[str, float]`

The state variables by name.

#### `derivative(t: float, y: ndarray, inputs: dict[str, Any]) → ndarray`

`dy/dt` at `(t, y)`, as `solve_ivp` calls it.

#### `advance(time: float, duration: float, inputs: dict[str, Any] | None = None) → None`

Integrate from `time` to `time + duration` with `inputs` held constant.

**Raises:**

[**CouplingError**](https://remipelloux.github.io/Modelly/apis/couple.html#modelly.couple.schedule.CouplingError) – if the integrator fails (`solve_ivp`’s message is included).

#### `start(coupling: Coupling) → None`

Publish the initial state.

#### `run(coupling: Coupling, time: float, duration: float) → None`

Read the inputs, integrate the step, publish the state.

#### `class Flow(name: str, rate: Callable[[dict[str, float], dict[str, Any]], float], source: str | None = None, target: str | None = None)`

A flow of a stock-flow model.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the flow’s name, the key of its total in `StockFlow.totals`.
- **rate** ([*collections.abc.Callable*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)*[**[*[*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]**, *[*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]**]**, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – `rate(stocks, inputs)`, the amount per unit time; a module-level function.
- **source** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – the stock it drains, or `None` for the outside.
- **target** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – the stock it fills, or `None` for the outside.

#### `class StockFlow(stocks: dict[str, float], flows: Sequence[Flow], reads: Iterable[str] = (), solver: Solver | None = None)`

Stocks joined by flows (system dynamics), a coupling component.

The state is the stocks followed by the running total of every flow; only the stocks are published to the coupling.

Start the stocks at the given values and every flow total at zero.

#### `property totals: dict[str, float]`

The amount moved by each flow since the start.

#### `derivative(t: float, y: ndarray, inputs: dict[str, Any]) → ndarray`

The stocks’ net flows followed by the flow rates.

#### `scipy_solve_ivp() → Callable[[...], Any]`

The `solve_ivp` of scipy, imported on first use and kept (scipy is heavy).

## ODEs in every agent

How to use them is in [ODEs in every agent](https://remipelloux.github.io/Modelly/agent_odes.html).

An ODE in every agent: per-agent state in columns, integrated as one batch.

`AgentODE` advances `dy/dt = rhs(t, y, params)` for every agent of one class, whose state variables and parameters are columns of `model.columns[agent_class]`. With an explicit method (`"RK45"`, `"RK23"`) it calls `solve_batch`: each agent keeps its own step size and tolerance, as if it had its own `solve_ivp` call, and the right-hand side runs once per stage for the whole population. With a stiff method (`"BDF"`, `"Radau"`, `"LSODA"`) it stacks the agents into one `solve_ivp` system and passes a block-diagonal Jacobian sparsity, since an agent’s equations involve only its own state.

Parameters may vary inside the step: `forcings` maps names to inputs of `modelly.couple.inputs` (a `Forcing` function of time or a `Series` table), read at every stage’s time. With `dense_output=True`, `at(t)` reads every agent’s state at any time of the last step, so an agent acting at a sub-step time sees the continuous value.

Events (`modelly.couple.events.ODEEvent`) are located per agent. A terminal event stops the agent at the crossing; after the whole population has been integrated, each event’s `action(table, rows, times)` runs, and the stopped agents resume from their crossing to the end of the step. Actions may change columns, not add or remove agents (do that in an agent phase), since rows are positions in the column table.

#### `class AgentODE(model: Any, agent_class: type, rhs: Callable[[...], Any], state: Sequence[str], params: Sequence[str] = (), reads: Iterable[str] = (), solver: Solver | None = None, events: Sequence[ODEEvent] = (), forcings: Mapping[str, Input] | None = None, dense_output: bool = False, delays: Mapping[str, Delay] | None = None)`

`dy/dt = rhs(t, y, params)` in every agent of a class, a coupling component.

Example

```default
>>> from modelly import Agent, Model
>>> from modelly.core.columns import Column
>>> class Cell(Agent):
...     mass = Column(float, default=1.0)
...     rate = Column(float, default=0.5)
...     def __init__(self, model, rate):
...         super().__init__(model)
...         self.rate = rate
>>> def decay(t, y, params):
...     return -params["rate"] * y
>>> model = Model(rng=1)
>>> cells = Cell.create_agents(model, 3, rate=[0.5, 1.0, 2.0])
>>> ode = AgentODE(model, Cell, decay, state=["mass"], params=["rate"])
>>> ode.advance(0.0, 1.0)
>>> model.columns[Cell].mass.round(4).tolist()
[0.6065, 0.3679, 0.1353]
```

Integrate the columns `state` of `agent_class`; `params` are read-only columns.

`reads` are coupling quantities passed to `rhs` in `params` by name, held over the step; `forcings` are inputs passed by name, read at each stage’s time. `dense_output` keeps the last step’s interpolant for `at`. `delays` maps names to `Delay` objects: `rhs` reads each agent’s state variable `tau` ago (`modelly.couple.delay`). `rhs`, the events’ functions and the forcings’ functions must be module-level functions or methods for the model to be saved.

#### `start(coupling: Coupling) → None`

Nothing to publish: the state lives in the agents’ columns.

#### `run(coupling: Coupling, time: float, duration: float) → None`

Read the inputs and integrate every agent over the step.

#### `advance(time: float, duration: float, inputs: dict[str, Any] | None = None) → None`

Integrate every agent from `time` to `time + duration`, writing the columns.

#### `at(t: Any, variable: str | None = None) → ndarray`

Every agent’s state at `t` inside the last step, a time or one per agent.

Returns the state variables, shape `(variables, agents)` in the rows of the column table, or one variable’s values with `variable`. After a terminal event an agent’s state is read on the integration that follows the event’s action.

**Raises:**

- [**CouplingError**](https://remipelloux.github.io/Modelly/apis/couple.html#modelly.couple.schedule.CouplingError) – without `dense_output`, before the first step, or when agents were added or removed since it.
- [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – for a time outside the last step.

Many independent ODE systems integrated at once, each with its own adaptive step.

`solve_batch` integrates `k` systems of `m` equations, `dy/dt = rhs(t, y, params)`, with `y` of shape `(m, k)`: one column per system (one per agent). It runs the same explicit Runge-Kutta pairs as `scipy.integrate.solve_ivp` (`"RK45"`, Dormand-Prince, and `"RK23"`, Bogacki-Shampine; their tableaux are read from scipy), with the same initial step selection, error norm and step-size controller, applied to every column separately. Each system therefore takes the steps it would take in its own `solve_ivp` call and is held to the same tolerance, while the right-hand side is evaluated once per stage for all of them, as numpy array operations.

Calling `solve_ivp` once per system gives the same answer, one Python solver per system. Stacking every system into one `solve_ivp` call is fast but different: it takes the smallest step any system needs, for all of them, and measures the error as the RMS over all `m * k` components, so one system’s error can grow to about `sqrt(k)` times the tolerance.

`rhs` receives `t` as an array of shape `(k,)` (each system is at its own time), `y` of shape `(m, k)` and `params`, a mapping whose arrays of length `k` are cut to the systems being advanced; scalars pass through. It returns an array of shape `(m, k)`.

References

Hairer, E., Norsett, S. P. and Wanner, G. (1993). Solving Ordinary Differential Equations I: Nonstiff Problems, 2nd ed., Sec. II.4. Springer.

#### `class BatchResult(t: ndarray, y: ndarray, stopped: ndarray, events: list[EventLog] = <factory>, nfev: int = 0, nsteps: ndarray = <factory>, nrejected: ndarray = <factory>, sol: BatchDense | None = None)`

What `solve_batch` returns.

**Variables:**

- **t** (*numpy.ndarray*) – each system’s final time, shape `(k,)`: the end of the span, or the time of the terminal event that stopped it.
- **y** (*numpy.ndarray*) – each system’s final state, shape `(m, k)`.
- **stopped** (*numpy.ndarray*) – which systems a terminal event stopped, shape `(k,)`.
- **events** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*modelly.couple.events.EventLog*](https://remipelloux.github.io/Modelly/apis/couple.html#modelly.couple.events.EventLog)*]*) – the crossings of every event, as an `EventLog` per event.
- **nfev** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – calls of `rhs`, each on every system still advancing.
- **nsteps** (*numpy.ndarray*) – accepted steps per system, shape `(k,)`.
- **nrejected** (*numpy.ndarray*) – rejected steps per system, shape `(k,)`.
- **sol** ([*modelly.couple.dense.BatchDense*](https://remipelloux.github.io/Modelly/apis/couple.html#modelly.couple.dense.BatchDense)* | **None*) – with `dense_output=True`, a `BatchDense`: `sol(t)` is every system’s state at `t` (one time, or one per system); otherwise None.

#### `solve_batch(rhs: Rhs, t_span: tuple[Any, Any], y0: Any, params: Mapping[str, Any] | None = None, *, method: str = 'RK45', rtol: float = 0.001, atol: float = 1e-06, events: Sequence[ODEEvent] = (), dense_output: bool = False) → BatchResult`

Integrate `k` independent systems from `t_span[0]` to `t_span[1]`.

**Parameters:**

- **rhs** – `rhs(t, y, params)` for `t` of shape `(k,)` and `y` of shape `(m, k)`.
- **t_span** – start and end, scalars or arrays of shape `(k,)`; the end must not be before the start.
- **y0** – the initial states, shape `(m, k)`.
- **params** – per-system arrays of length `k`, scalars, or inputs that vary in time (`modelly.couple.inputs`), passed to `rhs`.
- **method** – `"RK45"` (the default, as in `solve_ivp`) or `"RK23"`.
- **rtol** – the relative tolerance, as in `solve_ivp`.
- **atol** – the absolute tolerance, as in `solve_ivp`.
- **events** – `ODEEvent` objects located on every accepted step.
- **dense_output** – keep every step’s interpolant, to read the states at any time (`BatchResult.sol`), as `solve_ivp`’s `dense_output`.

**Returns:**

The final times and states, the event crossings, the work counts and, if asked, the dense output.

**Raises:**

[**CouplingError**](https://remipelloux.github.io/Modelly/apis/couple.html#modelly.couple.schedule.CouplingError) – for an unknown method or a step that falls below the minimum.

Events for `solve_batch`: where a function of the state crosses zero, per system.

An `ODEEvent` wraps `condition(t, y, params)`, which returns one value per system, as an event function of `solve_ivp` does for one. After every accepted step a system whose value changed sign (in the event’s `direction`) has the crossing located on the step’s dense output (the Runge-Kutta pair’s own interpolant, as `solve_ivp` uses), by bisection to the last bit of the step. A terminal event stops that system at its crossing; the others go on.

#### `class ODEEvent(condition: Callable[[ndarray, ndarray, Mapping[str, Any]], Any], terminal: bool = False, direction: float = 0.0, action: Callable[[Any, ndarray, ndarray], Any] | None = None)`

A zero crossing to locate in every system.

**Variables:**

- **condition** ([*collections.abc.Callable*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)*[**[**numpy.ndarray**, **numpy.ndarray**, *[*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]**]**, **Any**]*) – `condition(t, y, params)`, one value per system, shape `(k,)`.
- **terminal** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – stop a system at its first crossing.
- **direction** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – `1` for upward crossings only, `-1` for downward only, `0` for both.
- **action** ([*collections.abc.Callable*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)*[**[**Any**, **numpy.ndarray**, **numpy.ndarray**]**, **Any**] **| **None*) – for `AgentODE`, `action(table, rows, times)`, called after the integration with the agents’ column table, the rows that crossed and when. `solve_batch` ignores it.

#### `value(t: ndarray, y: ndarray, params: Mapping[str, Any]) → ndarray`

The condition’s value for each system.

#### `crossed(before: ndarray, after: ndarray) → ndarray`

Which systems crossed zero in this event’s direction (`solve_ivp`’s rule).

#### `class EventLog(rows: Any = <factory>, t: Any = <factory>, y: Any = <factory>)`

The crossings of one event: which system, when, and its state there.

**Variables:**

- **rows** (*Any*) – the system (column) of each crossing.
- **t** (*Any*) – the time of each crossing.
- **y** (*Any*) – the state at each crossing, shape `(m, crossings)`.

#### `add(rows: ndarray, t: ndarray, y: ndarray) → None`

Record crossings.

#### `close() → EventLog`

Join the recorded pieces into arrays, ordered by system then time.

## Inputs, dense output and delays

Inputs that change inside a step: `Forcing` (a function of time) and `Series` (a table).

A parameter of `solve_batch` or `AgentODE` given as an `Input` is evaluated at every stage’s time instead of being held over the step, so a temperature that varies through the day, a dosing schedule or a measured series drives each system at the times its own steps land on. `rhs` and the events’ conditions receive the evaluated value, never the `Input`.

from modelly.couple import Forcing, Series, solve_batch

daylight = Forcing(lambda t: np.maximum(np.sin(2 * np.pi * t), 0.0)) rainfall = Series([0.0, 1.0, 2.0], [0.0, 4.0, 1.0]) # linear between the points solve_batch(rhs, (0.0, 2.0), y0, {“light”: daylight, “rain”: rainfall})

A `Series` with two-dimensional values gives every system its own series (one column per system), and is cut with the systems like any per-system parameter.

#### `class Input`

A parameter that is a function of time; subclasses define `__call__` and `cut`.

#### `cut(rows: ndarray, k: int) → Input`

The input for the systems `rows` among `k`; itself when it is shared.

#### `class Forcing(function: Callable[[ndarray], Any])`

`function(t)`, called with each system’s time, shape `(systems,)`.

The result is a scalar or one value per system. The function must be a module-level function for a model holding it to be saved.

Example

```default
>>> Forcing(lambda t: 2 * t)(np.array([0.5, 1.0])).tolist()
[1.0, 2.0]
```

#### `class Series(times: Any, values: Any, kind: str = 'linear')`

Values at given times, read between them linearly or as the last value.

**Variables:**

- **times** (*Any*) – increasing times, shape `(n,)`.
- **values** (*Any*) – shape `(n,)` for one series shared by every system, or `(n, systems)` for one series per system.
- **kind** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"linear"` interpolation, or `"previous"` to hold each value until the next time. Before the first time and after the last the end values hold.

Example

```default
>>> Series([0.0, 2.0], [0.0, 10.0])(np.array([0.5, 3.0])).tolist()
[2.5, 10.0]
```

#### `cut(rows: ndarray, k: int) → Series`

The series of the systems `rows`: its columns when there is one per system.

#### `has_inputs(params: Mapping[str, Any]) → bool`

Whether any parameter is an `Input`.

#### `evaluated(params: Mapping[str, Any], t: ndarray) → Mapping[str, Any]`

`params` with every `Input` replaced by its value at `t`.

Dense output of `solve_batch`: every system’s state at any time of its span.

Each accepted step keeps the Runge-Kutta pair’s own interpolant (the polynomial `solve_ivp`’s `dense_output` uses), so `BatchDense(t)` reads a system inside a step at the accuracy of the integration, without integrating again. Each system can be read at its own time.

#### `interpolate(Q, h, y0, x) → ndarray`

The state at the fraction `x` of a step: `y0 + h * sum_d Q[d] * x**(d+1)`.

`Q` has shape `(degree, m, systems)`; `h` and `x` one value per system.

#### `class BatchDense(start: ndarray, y0: ndarray, final: ndarray = <factory>, segments: list[_Segment] = <factory>)`

The state of every system at any time between its start and its final time.

**Variables:**

- **start** (*numpy.ndarray*) – each system’s start time, shape `(k,)`.
- **y0** (*numpy.ndarray*) – each system’s initial state, shape `(m, k)`.
- **final** (*numpy.ndarray*) – each system’s final time (the end of its span, or where a terminal event stopped it).

#### `add(rows, t0, h, y0, Q) → None`

Keep one accepted step of the systems `rows`.

#### `clip(cols: ndarray, end: ndarray) → None`

End the last step of its systems `cols` at `end` (a terminal event).

#### `values(t: ndarray) → ndarray`

The states at `t` (one time per system), unchecked; a NaN time reads `y0`.

#### `column(t: ndarray, index: int) → ndarray`

`values(t)[index]`, the same numbers, interpolating only that variable.

#### `class StackedDense(solution: object, shape: tuple[int, int], start: ndarray, final: ndarray)`

Dense output of `k` systems stacked into one `solve_ivp` call (`OdeSolution`).

Delay differential equations in agents: a state variable read `tau` time units ago.

`Delay(variable, tau, before)` declared in `AgentODE(delays={name: Delay(...)})` passes `rhs` the value of each agent’s `variable` at `t - tau` as `params[name]`. The method of steps makes it exact: each step is integrated in chunks no longer than the shortest delay, so every delayed time falls in a part already integrated, whose dense output (the Runge-Kutta interpolant of every step) is kept in a `History`. Times before an agent’s first integration read `before`, a constant or a function of time.

The history is keyed by the agents’ unique ids, so agents added or removed between steps keep their own past; it keeps only what the longest delay can still reach, and it is saved with the model, so a resumed run reads the same past.

**Reference:**

Bellen, A. and Zennaro, M. (2003). Numerical Methods for Delay Differential Equations. Oxford University Press.

#### `class Delay(variable: str, tau: float, before: float | Callable[[ndarray], Any] = 0.0)`

A delayed state variable.

**Variables:**

- **variable** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the state variable (a column of `AgentODE`’s `state`).
- **tau** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the delay, positive.
- **before** ([*float*](https://docs.python.org/3/builtins/functions.html#float)* | *[*collections.abc.Callable*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)*[**[**numpy.ndarray**]**, **Any**]*) – the value before the agent’s first integration: a number or `before(t)`, `t` one time per agent.

#### `initial(t: ndarray) → ndarray`

The history before the first integration, at `t`.

#### `class History(reach: float, passes: list[_Pass] = <factory>)`

Every agent’s past states, as the dense output of the passes that integrated them.

#### `add(ids: ndarray, sol: BatchDense) → None`

Keep a pass of the agents `ids`.

#### `prune(now: float) → None`

Forget the passes that end before `now - reach`: no delay reaches them.

#### `read(index: int, ids: ndarray, t: ndarray, delay: Delay, cache: dict[int, tuple[Any, ...]] | None = None) → ndarray`

State variable `index` of the agents `ids` at times `t` (one each).

`cache` keeps each pass’s lookup of `ids` for the next read of the same ids.

#### `class Delayed(history: History, index: int, delay: Delay, ids: ndarray, lookups: dict[int, tuple[~typing.Any, ...]]=<factory>)`

The input `rhs` reads for one `Delay`: the variable at `t - tau` per agent.

#### `cut(rows: ndarray, k: int) → Delayed`

The input of the agents `rows`.

#### `chunks(start: float, end: float, longest: float) → list[tuple[float, float]]`

`[start, end]` cut into consecutive pieces no longer than `longest`.

## Stochastic equations and the mean-field limit

Stochastic differential equations for many independent systems at once.

`solve_sde_batch` integrates `k` systems of `m` Ito equations with diagonal noise,

dy = drift(t, y, params) dt + diffusion(t, y, params) dW,

`y` of shape `(m, k)`, each component driven by its own Wiener process, on a fixed step `dt`. Two schemes:

- `"euler"`: Euler-Maruyama, `y + a dt + b dW`; strong order one half.
- `"milstein"`: the derivative-free Milstein scheme of Kloeden and Platen (Sec. 11.1), `y + a dt + b dW + (b(y + b sqrt(dt)) - b(y)) (dW**2 - dt) / (2 sqrt(dt))`; strong order one for diagonal noise, with no derivative of `diffusion` to write.

The increments are drawn from the generator given (a model’s `rng`, so a run is a function of its seed and a saved model resumes the same stream), `dW = sqrt(dt) * N(0, 1)`, one array of shape `(m, k)` per step; or they are passed in (`noise=`), to drive several schemes or step sizes with one Brownian path, as a convergence study does.

References

Kloeden, P. E. and Platen, E. (1992). Numerical Solution of Stochastic Differential Equations. Springer.

Higham, D. J. (2001). An algorithmic introduction to numerical simulation of stochastic differential equations. SIAM Review, 43(3), 525-546.

#### `class SDEResult(t: ndarray, y: ndarray, path: ndarray | None = None)`

What `solve_sde_batch` returns.

**Variables:**

- **t** (*numpy.ndarray*) – the times of the steps, shape `(steps + 1,)`.
- **y** (*numpy.ndarray*) – the final states, shape `(m, k)`.
- **path** (*numpy.ndarray** | **None*) – with `keep_path=True`, the states at every time, `(steps + 1, m, k)`.

#### `steps_of(t0: float, t1: float, dt: float) → int`

The number of steps of size `dt` from `t0` to `t1` (the last may be shorter).

#### `increments(rng: Generator, shape: tuple[int, int], times: ndarray) → ndarray`

Wiener increments over `times`, shape `(steps, m, k)`, from `rng`.

#### `solve_sde_batch(drift: Coefficient, diffusion: Coefficient, t_span: tuple[float, float], y0: Any, params: Mapping[str, Any] | None = None, *, dt: float, rng: Generator | None = None, scheme: str = 'euler', noise: ndarray | None = None, keep_path: bool = False) → SDEResult`

Integrate `k` independent SDE systems on a fixed step.

**Parameters:**

- **drift** – `a(t, y, params)`, shape `(m, k)` (or broadcastable to it).
- **diffusion** – `b(t, y, params)`, the noise of each component (diagonal noise).
- **t_span** – start and end times, shared by every system.
- **y0** – the initial states, shape `(m, k)`.
- **params** – per-system arrays, scalars or inputs (`modelly.couple.inputs`).
- **dt** – the step; the last step ends at `t_span[1]` exactly.
- **rng** – the generator the increments are drawn from; needed unless `noise`.
- **scheme** – `"euler"` (Euler-Maruyama) or `"milstein"`.
- **noise** – the Wiener increments, shape `(steps, m, k)`, instead of drawing them.
- **keep_path** – keep the state at every step.

**Raises:**

[**CouplingError**](https://remipelloux.github.io/Modelly/apis/couple.html#modelly.couple.schedule.CouplingError) – for an unknown scheme, a step that is not positive, increments of the wrong shape, or neither a generator nor `noise`.

#### `coarsen(dws: ndarray, factor: int) → ndarray`

The increments of a path on a step `factor` times longer (sums of blocks).

A stochastic differential equation in every agent, its noise from the model’s seed.

`AgentSDE` advances `dy = drift dt + diffusion dW` for every agent of a class, the state variables and parameters being columns, with `solve_sde_batch` on a fixed sub-step `dt`. The Wiener increments come from `model.rng`, so a run is a function of its seed, and a checkpoint, which saves the generator’s state, resumes the same noise: a resumed run equals a straight one bit for bit. Agents added or removed between steps are followed, as for `AgentODE`.

#### `class AgentSDE(model: Any, agent_class: type, drift: Callable[[...], Any], diffusion: Callable[[...], Any], state: Sequence[str], params: Sequence[str] = (), *, dt: float, scheme: str = 'euler', reads: Iterable[str] = (), forcings: Mapping[str, Input] | None = None)`

`dy = drift(t, y, p) dt + diffusion(t, y, p) dW` in every agent of a class.

Example

```default
>>> from modelly import Agent, Model
>>> from modelly.core.columns import Column
>>> class Firm(Agent):
...     capital = Column(float, default=1.0)
>>> def growth(t, y, p):
...     return 0.05 * y
>>> def shocks(t, y, p):
...     return 0.2 * y
>>> model = Model(rng=1)
>>> firms = Firm.create_agents(model, 3)
>>> AgentSDE(model, Firm, growth, shocks, state=["capital"], dt=0.01).advance(0.0, 1.0)
>>> bool((model.columns[Firm].capital > 0).all())
True
```

Integrate the columns `state` of `agent_class` on the sub-step `dt`.

`params` are read-only columns, `reads` coupling quantities held over the step, `forcings` inputs read at each sub-step’s time. The functions must be module-level functions or methods for the model to be saved.

#### `start(coupling: Coupling) → None`

Nothing to publish: the state lives in the agents’ columns.

#### `run(coupling: Coupling, time: float, duration: float) → None`

Read the inputs and integrate every agent over the step.

#### `advance(time: float, duration: float, inputs: dict[str, Any] | None = None) → None`

Integrate every agent from `time` to `time + duration`, writing the columns.

The mean-field companion: an agent model’s ODE limit, run next to it, and the gap.

Many agent models have a deterministic limit as the population grows: the SIR equations for a well-mixed epidemic, Lotka-Volterra for predators and prey, the Bass equation for adoption. `Companion(model, MeanField(rhs, observe, names))` integrates that limit with `solve_ivp` from the model’s own starting state and, after each of the model’s steps, records the model’s aggregate state (`observe`) next to the ODE’s. `gap` is the largest difference, which shrinks like `1 / sqrt(N)` while sampling noise dominates; `gap_by_size` measures it over population sizes and fits that exponent, to show where the agent model departs from its limit (small populations, extinctions, network structure) and where it does not:

```default
from modelly.couple.meanfield import Companion, MeanField, bass

rates = {"innovation": 0.03, "imitation": 0.38}
companion = Companion(model, MeanField(bass, lambda m: [m.adoption], ("adopted",), rates))
for _ in range(100):
    model.step()
    companion.advance(model.scenario.dt)
companion.gap()
```

#### `sir(t: float, y: ndarray, p: Mapping[str, Any]) → ndarray`

Shares `(S, I, R)`: `S' = -beta S I`, `I' = beta S I - gamma I`, `R' = gamma I`.

#### `lotka_volterra(t: float, y: ndarray, p: Mapping[str, Any]) → ndarray`

Densities `(prey, predators)`: `x' = a x - b x y`, `y' = d b x y - c y`.

#### `bass(t: float, y: ndarray, p: Mapping[str, Any]) → ndarray`

Share adopted `F`: `F' = (innovation + imitation F) (1 - F)`.

#### `class MeanField(rhs: ~modelly.couple.meanfield.Rhs, observe: ~collections.abc.Callable[[~typing.Any], ~collections.abc.Sequence[float]], names: tuple[str, ...], params: ~collections.abc.Mapping[str, ~typing.Any] = <factory>, rtol: float = 1e-08, atol: float = 1e-10)`

The ODE limit of a model.

**Variables:**

- **rhs** (*modelly.couple.meanfield.Rhs*) – `rhs(t, y, params)` for the aggregate state `y`, as for `solve_ivp`.
- **observe** ([*collections.abc.Callable*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)*[**[**Any**]**, *[*collections.abc.Sequence*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)*[*[*float*](https://docs.python.org/3/builtins/functions.html#float)*]**]*) – `observe(model)`, the model’s aggregate state, the same variables.
- **names** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – the variables’ names.
- **params** ([*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]*) – passed to `rhs`.
- **atol** (*rtol**,*) – the tolerances of the integration.

#### `class Companion(model: Any, limit: MeanField)`

A model and its mean-field limit, side by side, from the same starting state.

Start the ODE from the model’s current aggregate state.

#### `advance(duration: float) → None`

Integrate the limit over `duration`; record it next to the model’s state.

Call it after each model step, with the time that step covers.

#### `gap() → float`

The largest difference between the model and its limit, over times and variables.

#### `frame() → Any`

A DataFrame with each variable twice: `<name>` (the model) and `<name>_limit`.

#### `class GapBySize(sizes: tuple[int, ...], gaps: tuple[float, ...], exponent: float)`

The mean gap at each population size, and its fitted power of the size.

#### `gap_by_size(run: Callable[[int, int], Companion], sizes: Sequence[int], seeds: Sequence[int]) → GapBySize`

`run(size, seed)` returns a finished companion; the gaps and their exponent.

The exponent is the slope of `log gap` against `log size`: about `-0.5` while the gap is sampling noise, flatter where the model departs from its limit.
