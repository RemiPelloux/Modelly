# ODEs in every agent

Some models need continuous dynamics inside each agent: the virus in a host, the energy budget of an animal, the capital of a firm, the membrane potential of a neuron. `modelly.couple` gives every agent its own ODE and integrates the whole population at once:

What it is

When to use it

solve_batch

solve_ivp for many independent systems: each keeps its own adaptive step and tolerance, the right-hand side runs once per stage for all of them

integrating many systems outside a model, or inside your own step

ODEEvent

a zero crossing located per system on the step’s interpolant, terminal or not, upward, downward or both

“the moment the virus passes this level”

AgentODE

a coupling component: the state variables are columns of an agent class, integrated with solve_batch (or a stiff solve_ivp) each step, events calling back into the model

an ODE per agent inside a model

They need only numpy and scipy and work the same on Windows, macOS and Linux. For a single ODE or a stock-flow model per model, see [Coupling fields and ODEs](https://remipelloux.github.io/Modelly/dev/coupling.html).

## `solve_batch`: `solve_ivp` for a population

`solve_ivp` integrates one system. Given `k` systems of `m` equations, `solve_batch` takes the state as an array of shape `(m, k)`, one column per system, and a right-hand side written with numpy, so it applies to every column at once:

```python
import numpy as np
from modelly.couple import solve_batch

def decay(t, y, params):
    """t has shape (k,), y has shape (m, k); params holds arrays of length k, or scalars."""
    return -params["rate"] * y

rates = np.array([0.5, 1.0, 2.0])
result = solve_batch(
    decay, (0.0, 1.0), np.ones((1, 3)), {"rate": rates}, rtol=1e-8, atol=1e-10
)
result.y  # array([[0.60653066, 0.36787944, 0.13533528]])
result.nsteps  # accepted steps per system, as len(sol.t) - 1 from solve_ivp
```

`t_span` can give each system its own start and end (arrays of length `k`), and `params` arrays whose last axis has length `k` are cut to the systems being advanced, so each system sees its own parameters. A parameter that is not per system (a matrix, a constant) is passed whole.

### The same answer as `solve_ivp`, system by system

`solve_batch` runs scipy’s own Runge-Kutta pairs, `"RK45"` (Dormand-Prince, the default) and `"RK23"` (Bogacki-Shampine), reading their coefficients from scipy, with scipy’s initial step selection, error norm and step-size controller, applied to each column separately. Each system therefore takes exactly the steps it would take in its own `solve_ivp` call, and ends where that call ends to round-off: the tests check, on 200 systems with random parameters, for both methods and at loose and tight tolerances, that every system’s number of accepted steps equals `solve_ivp`’s and that the final states agree to `1e-9` relative (`tests/couple/test_batch.py`). The difference is the order of floating-point sums.

### And one stacked `solve_ivp` call?

Stacking every agent into one long vector and calling `solve_ivp` once is the usual trick. It is fast, and it is a different method:

- **One step size for everyone.** The solver takes, at every moment, the smallest step any agent needs, for all agents. When their dynamics peak at different times (infections that start on different days, animals in different patches), each agent is stepped through every other agent’s hard moments: more work, and usually more accuracy than it asked for.
- **Error measured over the whole population.** `solve_ivp` controls the RMS of the error over all `m * k` components, so how closely one agent is followed depends on all the others.
- **An agent’s numbers depend on the population.** Add one agent, remove one, or reorder them, and every other agent’s trajectory changes in its last digits or more, since the shared steps change. With `solve_batch` an agent’s result is the same, bit for bit, whether it is integrated alone or among a hundred thousand others (`tests/couple/test_batch.py` checks it): every operation is per column.

So the two answer different questions. `solve_batch` gives each agent what its own `solve_ivp` call would give, the semantics of a loop of `solve_ivp` calls, at the speed of array code; the measured times are in [Performance](https://remipelloux.github.io/Modelly/dev/agent_odes.html#performance).

## Events

An `ODEEvent` wraps an event function as `solve_ivp`’s `events=` does, one value per system:

```python
from modelly.couple import ODEEvent

def below_half(t, y, params):
    return y[0] - 0.5

half_life = ODEEvent(below_half, terminal=True, direction=-1)
result = solve_batch(
    decay,
    (0.0, 10.0),
    np.ones((1, 3)),
    {"rate": rates},
    rtol=1e-10,
    atol=1e-12,
    events=[half_life],
)
result.t  # each system stopped at ln 2 / rate
result.stopped  # array([ True,  True,  True])
result.events[0].rows  # which system crossed ...
result.events[0].t  # ... when ...
result.events[0].y  # ... and its state there
```

After every accepted step, a system whose value changed sign in the event’s `direction` has the crossing located on the step’s dense output, the Runge-Kutta pair’s own interpolant (the one `solve_ivp` uses), by bisection to below one unit in the last place of the step. A terminal event stops that system at the crossing and the others go on; a non-terminal event records every crossing. The sign rule is `solve_ivp`’s.

## `AgentODE`: an ODE in every agent of a model

`AgentODE` is a [coupling](https://remipelloux.github.io/Modelly/dev/coupling.html) component. Its state variables and parameters are [columns](https://remipelloux.github.io/Modelly/dev/performance.html) of an agent class, so each agent still reads its own values (`host.virus`), the model sees all of them as arrays (`model.columns[Host].virus`), and the ODE writes them back in place each step. Events carry an `action(table, rows, times)`, called after the step’s integration with the column table, the rows that crossed and when. A terminal event’s agents resume from their crossing to the end of the step after the action has run, so an action can reset the state (a neuron that fires and resets).

### A worked example: viral dynamics in every host

Each host carries the target-cell-limited model of influenza (Baccam et al., 2006): target cells, infected cells and virus. A host is infectious while its virus load is above a threshold; the moments it crosses the threshold are events, located to the instant rather than rounded to the day. Between hosts, a daily phase exposes susceptible hosts with a chance that grows with the share of infectious hosts.

```python
import numpy as np

from modelly import Agent, Model
from modelly.core.columns import Column
from modelly.couple import AgentODE, Coupling, ODEEvent, Phase, Solver

THRESHOLD = 1e-2  # virus load above which a host is infectious

class Host(Agent):
    cells = Column(float, default=1.0)  # target cells, as a fraction
    infected = Column(float, default=0.0)  # infected cells
    virus = Column(float, default=0.0)
    beta = Column(float, default=10.0)  # this host's infection rate
    infectious = Column(bool, default=False)
    onset = Column(float, default=np.nan)  # when its virus crossed the threshold

def within_host(t, y, p):
    cells, infected, virus = y
    infection = p["beta"] * cells * virus
    return np.array(
        [-infection, infection - 2.0 * infected, 20.0 * infected - 3.0 * virus]
    )

def above(t, y, p):
    return y[2] - THRESHOLD

def becomes_infectious(table, rows, times):
    table["infectious"][rows] = True
    table["onset"][rows] = times

def recovers(table, rows, times):
    table["infectious"][rows] = False

class Outbreak(Model):
    def __init__(self, hosts=10_000, contacts=8.0, rng=42):
        super().__init__(rng=rng)
        Host.create_agents(self, hosts)
        self.table = self.columns[Host]
        self.table.beta[:] = self.rng.lognormal(np.log(10.0), 0.5, hosts)
        self.table.virus[:10] = 1e-3  # ten index cases
        self.contacts = contacts
        events = [
            ODEEvent(above, direction=1, action=becomes_infectious),
            ODEEvent(above, direction=-1, action=recovers),
        ]
        self.coupling = Coupling()
        self.coupling.add(Phase(self.transmit))
        self.coupling.add(
            AgentODE(
                self,
                Host,
                within_host,
                state=["cells", "infected", "virus"],
                params=["beta"],
                events=events,
                solver=Solver(rtol=1e-6, atol=1e-9),
            ),
            phase=1,
        )
        self.coupling.build()

    def transmit(self):
        table = self.table
        susceptible = table.virus == 0.0
        chance = 1 - np.exp(-self.contacts * table.infectious.mean() * 0.1)
        table.virus[susceptible & table.draw(chance)] = 1e-6

    def step(self):
        self.coupling.step(1.0)  # one day

model = Outbreak()
model.run_for(60)
```

Ten thousand hosts over sixty days take about four seconds on a laptop core, and the same seed gives the same outbreak bit for bit (`tests/couple/test_within_host.py` runs this model).

### Inputs from the rest of the model

`reads=["temperature"]` passes coupling quantities to the right-hand side in `params`, held over the step, as an `ODE` reads them. Per-agent inputs are columns listed in `params`, written by an agent phase before the ODE’s phase.

### Inputs that change inside the step

An input that varies faster than the model’s step (daylight, a dosing schedule, a measured temperature series) is passed as a forcing. The right-hand side receives its value at each stage’s time, so every agent sees it at the times its own steps land on:

```python
from modelly.couple import AgentODE, Forcing, Series

def daylight(t):
    return np.maximum(np.sin(2 * np.pi * t), 0.0)

temperature = Series([0.0, 0.5, 1.0], [12.0, 21.0, 12.0])  # linear between the points
ode = AgentODE(
    model,
    Animal,
    energy,
    state=["reserve"],
    params=["mass"],
    forcings={"light": Forcing(daylight), "temp": temperature},
)
```

`Forcing(function)` calls `function(t)` with one time per agent; it returns a scalar or one value per agent. `Series(times, values)` reads a table linearly between its times (`kind="previous"` holds each value until the next time) and holds the end values outside them; values of shape `(times, agents)` give each agent its own series. The same inputs work in `solve_batch` as entries of `params`, and on the stiff path. Against `solve_ivp` with the forcing written inside the function, every system takes the same steps and ends at the same value (`tests/couple/test_inputs_dense.py`).

### Reading the state inside the step

With `dense_output=True`, `ode.at(t)` returns every agent’s state at a time inside the last step: one time, or one per agent, read on the step’s own interpolant (the polynomial `solve_ivp`’s `dense_output` uses), without integrating again. An agent acting at a sub-step time, such as a host tested at 14:00, sees the continuous value:

```python
ode = AgentODE(
    model,
    Host,
    tiv,
    state=["cells", "infected", "virus"],
    params=["beta"],
    dense_output=True,
)
ode.advance(day, 1.0)
load_at_test = ode.at(day + test_hour / 24, "virus")  # one value per host
```

After a terminal event, a time past the crossing reads the integration that follows the event’s action, so a neuron read just after it fires reads its reset value. `at` refuses a time outside the last step and a population that changed since it. `solve_batch(..., dense_output=True)` returns the same reader as `result.sol`, with `result.sol(t)` of shape `(m, k)`.

### Stiff systems

With `Solver(method="BDF")`, `"Radau"` or `"LSODA"`, `AgentODE` stacks the agents into one `solve_ivp` system and passes the Jacobian’s sparsity pattern: block diagonal, since an agent’s equations involve only its own state, so the implicit solver’s linear algebra grows with the number of agents rather than its square (LSODA takes no pattern and gets none). The stiff path shares one step between agents, as above; events need an explicit method.

## Performance

`benchmarks/ode/compare.py` integrates the within-host model above over ten days in two populations: `alike`, whose parameters vary by 10% between hosts, and `diverse`, whose infection rate, virus production and initial virus span one to four orders of magnitude. It compares a loop of `solve_ivp` calls, one stacked `solve_ivp` call and `solve_batch`, all `RK45` at `rtol=1e-6`, `atol=1e-9`, one thread on one pinned core. “Worst error” is the largest error of any host against a reference solved at `rtol=1e-12`, in units of that host’s own tolerance.

Population

Agents

Loop of solve_ivp

One stacked solve_ivp

solve_batch

solve_batch vs loop

Stacked time over solve_batch time

alike

10

24.5 ms (0.15)

4.4 ms (0.24)

7.8 ms (0.15)

3x

0.57x

alike

100

242 ms (0.18)

5.0 ms (0.22)

8.7 ms (0.18)

28x

0.57x

alike

1,000

2,504 ms (0.18)

15.7 ms (0.22)

24.0 ms (0.18)

104x

0.65x

alike

10,000

38,987 ms (0.18)

85.7 ms (0.26)

125 ms (0.18)

313x

0.69x

alike

100,000

not run

1,549 ms (0.28)

1,705 ms (0.18)

0.91x

diverse

10

22.1 ms (8.3)

7.9 ms (0.81)

11.6 ms (8.3)

2x

0.68x

diverse

100

352 ms (15)

17.2 ms (2.3)

26.3 ms (15)

13x

0.65x

diverse

1,000

3,103 ms (19)

49.5 ms (7.7)

68.6 ms (19)

45x

0.72x

diverse

10,000

39,845 ms (21)

283 ms (6.1)

302 ms (21)

132x

0.94x

diverse

100,000

not run

4,420 ms (10)

3,053 ms (29)

1.45x

Times are the best of five runs (one run for the loop past 1,000 agents; the loop is not run at 100,000, where it would take about six minutes); the worst error is in brackets. Measured with CPython 3.15, numpy 2.5 and scipy 1.18 on one core of an x86-64 laptop that was not idle (load average 7 to 12), so read the ratios rather than the last digit; `results.json` next to the script has every number.

- **Against a loop of `solve_ivp` calls**, `solve_batch` gives the same answers (the same worst error, agent for agent) 100 to 300 times faster from a thousand agents up.
- **Against one stacked call**, `solve_batch` takes 1.1 to 1.8 times as long when the agents are alike or fewer than 100,000, and is faster (1.45 times at 100,000) when they differ, since the stacked call then steps everyone through every agent’s peak. The stacked call is also more accurate on the diverse population, for the same reason: its shared small steps follow each agent more closely than that agent’s own tolerance asks. If that is the accuracy you want, ask `solve_batch` for it with a smaller `rtol`; if you want each agent’s result not to depend on the others, the stacked call cannot give it.

## Delay equations

When a rate depends on the state some time ago (an immune response that lags the virus, a maturation time, a gestation), declare the delayed variable and read it from `params`:

```python
from modelly.couple import AgentODE, Delay

def lagged(t, y, p):
    return -p["rate"] * p["past"]  # y'(t) = -rate * y(t - 1)

ode = AgentODE(
    model,
    Cell,
    lagged,
    state=["y"],
    params=["rate"],
    delays={"past": Delay("y", tau=1.0, before=1.0)},
)
```

`p["past"]` is each agent’s `y` at `t - tau`. `AgentODE` uses the method of steps: it cuts each step into pieces no longer than the shortest delay, so every delayed time falls in a part already integrated, and reads it on the dense output of the steps that integrated it. Before an agent’s first integration it reads `before`, a number or a function of time. The past is kept by the agents’ unique ids, so agents added or removed between steps keep their own; only as much as the longest delay can reach is kept, and it is saved with the model, so a resumed run reads the same past. For `y' = -a y(t - 1)` with `y = 1` before 0 the result equals the piecewise-polynomial closed form to `rtol` whatever the model’s step (`tests/couple/test_delay.py`). Delays need an explicit method.

## Stochastic equations

`AgentSDE` integrates an Ito equation with diagonal noise in every agent, `dy = drift dt + diffusion dW`, on a fixed sub-step `dt`:

```python
from modelly.couple import AgentSDE

def growth(t, y, p):
    return 0.05 * y

def shocks(t, y, p):
    return p["volatility"] * y  # geometric Brownian motion, one volatility per firm

sde = AgentSDE(
    model,
    Firm,
    growth,
    shocks,
    state=["capital"],
    params=["volatility"],
    dt=0.01,
    scheme="milstein",
)
```

The Wiener increments are drawn from `model.rng`, so a run is a function of its seed and a checkpoint, which saves the generator, resumes the same noise bit for bit. `scheme="euler"` is Euler-Maruyama, of strong order one half; `scheme="milstein"` is the derivative-free Milstein scheme of Kloeden and Platen, of strong order one for diagonal noise, with no derivative of the diffusion to write. Measured on geometric Brownian motion against its exact solution, over 4,000 paths driven by one Brownian path each at five step sizes, the fitted orders are 0.53 and 0.95 (`tests/couple/test_sde.py`). `solve_sde_batch` is the same integrator without a model; `noise=` drives it with given increments, to compare schemes on one path.

## The mean-field limit

Many agent models have an ODE limit as the population grows. `Companion` runs that limit next to the model, from the model’s own starting state, and records both after each step:

```python
from modelly.couple import Companion, MeanField
from modelly.couple.meanfield import bass

limit = MeanField(
    bass, lambda m: [m.adoption], ("adopted",), {"innovation": 0.03, "imitation": 0.38}
)
companion = Companion(model, limit)
for _ in range(steps):
    model.step()
    companion.advance(model.scenario.dt)
companion.gap()  # the largest difference; companion.frame() has both curves
```

`modelly.couple.meanfield` has the limits of the well-mixed SIR epidemic (`sir`), Lotka-Volterra (`lotka_volterra`) and Bass diffusion (`bass`); any `solve_ivp`-style function works. `gap_by_size(run, sizes, seeds)` measures the gap over population sizes and fits its power of the size: on the Bass zoo model, from 250 to 16,000 households, the exponent is -0.47, the `1 / sqrt(N)` of sampling noise (`tests/couple/test_meanfield.py`). A flatter exponent shows where a model departs from its limit: network structure, extinctions, or its own time step, which leaves a floor of the order of `dt`.

## Gradients of ODE parameters

`modelly.diff.ode.ode_phase(rhs, state)` puts an ODE per agent into a [differentiable model](https://remipelloux.github.io/Modelly/dev/differentiable.html), so `check_gradients` and `GradientCalibration` fit ODE parameters by gradient. It integrates with fourth-order Runge-Kutta on fixed sub-steps and JAX differentiates through them; see [Differentiable models](https://remipelloux.github.io/Modelly/dev/differentiable.html#odes-in-a-differentiable-model).

## Checkpoints and determinism

`solve_batch` draws no random numbers and starts every call from the state it is given, so an `AgentODE` model saved and loaded resumes bit for bit (`tests/couple/test_agent_ode.py`). The sums run through `einsum` rather than BLAS, so they do not depend on the number of BLAS threads. Across platforms, the step-size controller uses powers that are not correctly rounded, so compare results between machines with a tolerance, as for any `solve_ivp` result.

## Limits

- Batched methods are `"RK45"` and `"RK23"`; `"DOP853"` and the implicit methods run through `solve_ivp` (the stiff path above, with one step shared by all agents).
- The right-hand side and event functions must be written with numpy, for arrays of shape `(m, k)`; a function written for one system with Python `if` statements has to be rewritten with `np.where`. They must be module-level functions or methods for the model to be saved.
- A parameter is cut per system when its last axis has length `k`; a shared array that happens to have that length would be cut too, so give it another shape.
- ODEEvent actions may change columns but not add or remove agents (rows are positions in the column table): add or remove them in an agent phase.
- An agent whose state does not move still costs a few steps per call, from the initial step heuristic (about seven for a day), as in `solve_ivp`.
- Coupling quantities in `reads` are held over the step, as for `ODE`; an input that changes inside the step is a forcing (above).

## References

- Kloeden, P. E. and Platen, E. (1992). *Numerical Solution of Stochastic Differential Equations*. Springer.
- Bellen, A. and Zennaro, M. (2003). *Numerical Methods for Delay Differential Equations*. Oxford University Press. Baccam, P., Beauchemin, C., Macken, C. A., Hayden, F. G. and Perelson, A. S. (2006). Kinetics of influenza A virus infection in humans. *Journal of Virology*, 80(15), 7590-7599.

Hairer, E., Norsett, S. P. and Wanner, G. (1993). *Solving Ordinary Differential Equations I: Nonstiff Problems*, 2nd ed. Springer.
