# GPU arrays

`modelly.gpu` runs the array side of a model (column phases, cohort tables and the operators of
a cell space) on a GPU, with one setting, and draws the same random numbers there as on the
CPU. The agents stay Python objects on the host; their columns are copied to the device, the
step phases run there, and the results come back when the agents need them.

| Backend | Where it runs | Install |
|---|---|---|
| `numpy` | the CPU, always; the fallback of every GPU path | nothing |
| `cupy` | NVIDIA GPUs through CUDA, Linux and Windows | `pip install "modelly-abm[gpu]"` (CuPy wheels bundle the CUDA runtime; only the driver is needed) |
| `jax` | CPU everywhere; CUDA on Linux and Windows; Metal on macOS where `jax-metal` supports it | `pip install "modelly-abm[diff]"`, plus `"jax[cuda13]"` for NVIDIA or `jax-metal` for Apple GPUs |

Metal has not been tested in Modelly's own runs: the JAX path uses only operations every JAX
backend has, but no Apple GPU was available to check it.

## One setting

```python
from modelly.gpu import get_backend

backend = get_backend("cupy")    # or "jax", "numpy", "auto" (a GPU backend if one loads)
```

`get_backend()` without a name reads the `MODELLY_BACKEND` environment variable (numpy when it
is unset), so the same script runs on a laptop and on a GPU machine:

```bash
MODELLY_BACKEND=cupy python run.py
```

A backend that cannot load (no CuPy, no device) falls back to numpy with a
`BackendFallbackWarning`; `get_backend(name, strict=True)` raises instead. `import modelly` and
the numpy backend import neither CuPy nor JAX, and nothing in the CPU column code changed: a
model that does not ask for a GPU runs exactly as before.

## A column phase on the GPU

The `modelly-gpu` variant of the grid epidemic playbook
(`benchmarks/playbooks/grid_epidemic/modelly_gpu.py`) is the column variant with its step on
the device:

```python
from modelly.gpu import DeviceCellIndex, DeviceTable, PhiloxStream, get_backend

backend = get_backend()
stream = PhiloxStream(seed, stream=0, backend=backend)
cells = DeviceCellIndex(model.index, backend)           # the grid's adjacency, once
people = DeviceTable.from_columns(model.columns[Person], stream)


def step():
    xp = people.xp                                       # numpy, cupy or jax.numpy
    rows = cells.random_neighbor(people.row, stream)     # a random walk on the grid
    people.row = rows
    infected = people.state == I
    exposure = cells.counts(rows, infected)[rows]        # infected cellmates
    catches = (people.state == S) & people.draw(infect[exposure])
    people.state = xp.where(catches, I, people.state)


people.write_to(model.columns[Person])                  # back to the agents
```

Updates are functional: `people.state = ...` replaces the column, because JAX arrays cannot be
written in place. The population is fixed while the columns are on the device; add and remove
agents on the host table and copy again.

| Host | Device | Notes |
|---|---|---|
| `ColumnTable` | `DeviceTable` | `draw`, `thin`, `set_where`, `write_to`, `to_dataframe` |
| `CohortTable` | `DeviceCohortTable` | `add`, `thin`, `draw`, `split`, `compact`, `merge`, `total`, `totals_by` |
| `CellIndex` | `DeviceCellIndex` | `counts`, `neighbor_sum`, `random_neighbor`, `to_layer` |
| `model.rng` | `PhiloxStream` | `random`, `integers`, `bernoulli`, `binomial`, `draws()` |

## The same numbers on every device

`PhiloxStream(seed, stream)` is a counter-based generator: Philox4x32-10 (Salmon et al., 2011)
keyed by the seed. Element `i` of draw number `c` is computed from the counter
`(i // k, sub, c, stream)` alone, with no state carried from one number to the next, so a GPU
computes the same number for agent `i` as the CPU, whatever the order, the batch or the device.
The implementation is checked against the published Random123 known-answer vectors, and
numpy, the CuPy kernels and JAX are checked against each other bit for bit
(`tests/gpu/test_philox.py`, `test_streams.py`). Numpy's own `numpy.random.Philox` is the
4x64 variant, so its streams are different numbers.

| Draw | Construction | Same on every backend |
|---|---|---|
| uniform, float64 | `((w0 >> 5) * 2**26 + (w1 >> 6)) / 2**53`, numpy's construction | yes (JAX: with `jax_enable_x64`) |
| uniform, float32 | `(w >> 8) / 2**24` | yes |
| integers in `[0, high)` | `high * w >> 32`, bias below `high / 2**32` | yes |
| Bernoulli(p) | uniform `< p` | yes, for the same `p` |
| Binomial(n, p) | inversion below a mean of 10, BTRS (Hörmann 1993) above | inversion: yes; BTRS: see below |

Both binomial samplers are exact: their variates have the Binomial law (tested by chi-square
against the probability mass function). The inversion decides with `+ - * /` and comparisons
only, which IEEE 754 makes identical everywhere. BTRS takes logarithms, whose last bit may
differ between numpy, CUDA and XLA; a different bit changes a variate only when a uniform falls
within one rounding error of the acceptance bound, so the results are the same in practice (they
were in every test and every playbook run) and the same law always.

Without `jax.config.update("jax_enable_x64", True)`, JAX has no 64-bit types: its floats are
float32 and its integers int32, so its uniforms are the float32 ones and its runs differ from
numpy's float64 runs (in the same law). Integers drawn by `bits` and `integers` are the same in
both modes.

## Exactness against the CPU

What "equal" means for each kind of state:

| State | GPU against the numpy run of the same code |
|---|---|
| integer columns (states, counts, cell rows, days) | bit for bit |
| integer sums (`counts`, `neighbor_sum` of integers, `totals_by`) | bit for bit |
| float sums (`counts` with float weights, `neighbor_sum` of floats) | within a few ulps: additions in another order |
| float elementwise arithmetic | bit for bit for `+ - * /`; `exp`, `log`, `pow` within one ulp |

A phase whose integer outcome depends on a transcendental function (the grid epidemic's
`1 - (1 - beta) ** k`) can tabulate it once on the host, as the playbook does, so the
comparison that decides a draw is the same on every device. The comparison with the CPU
column variant (`modelly`), which draws from `model.rng`, is in distribution, like every
other playbook variant.

## Populations larger than the GPU

`plan_memory(rows, bytes_per_row, backend)` sizes batches to half the free device memory (or a
`budget`), and `run_batched(plan, phase, columns, backend)` copies each batch of host rows in,
runs the phase and copies the outputs back. A phase that draws by position
(`draw.random(n, start=start)`) gives the same numbers whatever the batch size, so a batched run
equals the run in one batch bit for bit. Only phases whose rows do not read one another batch
exactly; a reduction over rows (counts per cell) is the sum of per-batch reductions, which the
caller adds.

## Speed

Measured on a laptop RTX 5050 (8 GB): the grid epidemic's 60 steps at 10 million agents run
34x faster on CuPy than the CPU column variant; see [Performance](performance.md#gpu-backend)
for the conditions and the other numbers. What does not get faster:

- **Small tables.** A cohort table has fewer than two hundred rows; on a GPU each operation is a
  kernel launch of a few microseconds plus a device synchronisation for every data-dependent
  size, so `insect_cohorts` runs slower on CuPy than on numpy. Use the GPU from about a hundred
  thousand rows.
- **JAX and changing shapes.** JAX compiles every operation for every new array shape. A
  `DeviceCohortTable` changes length every day, so on JAX each step recompiles; the binomial
  sampler pads its input to a power of two to bound that, but the cohort playbook still takes
  about a second per step on JAX's CPU backend. Fixed-size column phases (a population that
  does not change size) compile once.
- **The numpy fallback** draws Philox numbers with array operations, about 50 ns per number,
  several times slower than `model.rng`. It is the reference the GPU runs are checked against,
  not a fast CPU path: keep the `ColumnTable` code for CPU runs.
