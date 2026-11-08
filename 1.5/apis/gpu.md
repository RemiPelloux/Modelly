# GPU

`modelly.gpu` runs column phases, cohort tables and cell-space operators on numpy, CuPy or JAX, with counter-based random numbers that are the same on every backend. How to use it is in [GPU arrays](https://remipelloux.github.io/Modelly/gpu.html).

## Backends

Array backends: numpy on the CPU, CuPy on CUDA GPUs, JAX on CPU, CUDA or Metal.

A [`Backend`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.backend.Backend) wraps one array library (`backend.xp`, used like numpy) and adds the handful of operations whose spelling differs between them: a functional scatter (JAX arrays are immutable), per-bin sums, the Philox rounds, device synchronisation and free memory. Everything in `modelly.gpu` is written against it, so one setting moves a model between devices:

```default
backend = get_backend("cupy")      # or "jax", "numpy", "auto"
MODELLY_BACKEND=cupy python run.py # the same, for get_backend()
```

A backend that cannot be loaded falls back to numpy with a [`BackendFallbackWarning`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.backend.BackendFallbackWarning) (`strict=True` raises instead), so a model written for the GPU always runs. CuPy and JAX are imported only when their backend is requested: `import modelly` and the numpy backend never load them.

#### `exception BackendUnavailableError`

The requested array backend cannot be loaded on this machine.

#### `exception BackendFallbackWarning`

A GPU backend was requested but numpy runs instead.

#### `class Backend`

The numpy backend, and the interface the GPU backends implement.

**Variables:**

- **name** – `"numpy"`, `"cupy"` or `"jax"`.
- **xp** – the array namespace.
- **gpu** – whether arrays live on an accelerator.

Bind numpy as the array namespace.

#### `property float_dtype: Any`

The widest float the backend computes in (float64, or float32 on 32-bit JAX).

#### `property int_dtype: Any`

The widest integer the backend stores (int64, or int32 on 32-bit JAX).

#### `property device: str`

A short description of where the arrays live.

#### `asarray(values: Any, dtype: Any = None) → Any`

`values` as an array of this backend (copied to the device if needed).

#### `to_numpy(array: Any) → ndarray`

A numpy copy (or view) of `array` on the host.

#### `put(array: Any, index: Any, values: Any) → Any`

A copy of `array` with `array[index] = values`; `array` is unchanged.

#### `segment_add(index: Any, weights: Any, n: int) → Any`

`out[b]` = sum of `weights` where `index == b`, for `b < n`.

Integer and boolean weights give exact integer sums (below 2**53); float sums may differ in the last bits between devices, which add in a different order.

#### `bincount(index: Any, n: int) → Any`

How many times each bin `b < n` occurs in `index`.

#### `argsort_stable(values: Any) → Any`

Indices that sort `values`, equal values keeping their order.

#### `philox(block: Any, words: tuple[int, int, int], key: tuple[int, int])`

Philox4x32-10 at counters `(block, *words)`: four uint32 arrays.

#### `synchronize(array: Any = None) → None`

Wait for the device to finish (for timing); numpy is always finished.

#### `free_bytes() → int`

Bytes available for new arrays: available host memory for numpy (0 if unknown).

#### `get_backend(name: str | Backend | None = None, strict: bool = False) → Backend`

The array backend `name`: `"numpy"`, `"cupy"`, `"jax"` or `"auto"`.

**Parameters:**

- **name** – a backend name, a Backend (returned as is), or None for the `MODELLY_BACKEND` environment variable (numpy when unset).
- **strict** – raise BackendUnavailableError instead of falling back to numpy.

#### `available_backends() → list[str]`

The backends that load on this machine, numpy first.

The CuPy backend: arrays on an NVIDIA GPU through CUDA (Linux and Windows).

`pip install "modelly-abm[gpu]"` installs `cupy-cuda13x`, whose wheels carry the CUDA runtime and NVRTC: no CUDA toolkit is needed, only the NVIDIA driver. The Philox rounds run in compiled elementwise kernels, one per kind of draw (words, uniforms, bounded integers), each computing an element’s block and converting it in registers; everything else is CuPy’s numpy-compatible API. CuPy is imported when the backend is created, never by `import modelly`.

The kernels follow the numpy code of `modelly.gpu.philox` and `modelly.gpu.streams` operation for operation (integer arithmetic, and float conversions that are exact), so they give numpy’s numbers bit for bit.

#### `class CupyBackend`

Arrays on the current CUDA device, through CuPy.

Import CuPy, check a device answers and declare the Philox kernels.

#### `property device: str`

The CUDA device’s name.

#### `to_numpy(array: Any) → ndarray`

Copy `array` from the device to a numpy array.

#### `argsort_stable(values: Any) → Any`

CuPy’s argsort is a stable radix sort.

#### `philox(block: Any, words: tuple[int, int, int], key: tuple[int, int])`

The Philox rounds at every block, one kernel launch: four word arrays.

#### `bits_at(positions: Any, words: tuple, key: tuple) → Any`

The uint32 word of the elements at `positions` (four per block).

#### `bounded_at(positions: Any, high: Any, words: tuple, key: tuple) → Any`

`high * word >> 32` for the elements at `positions`.

#### `uniform_at(positions: Any, words: tuple, key: tuple, single: bool) → Any`

Uniforms of the elements at `positions`: float32 (24 bits) or float64 (53).

#### `neighbor_at(rows: Any, csr: tuple, words: tuple, key: tuple) → Any`

`random_neighbor` in one kernel: the uniform pick and the gather, per row.

`csr` is `(indptr, indices)` as int64 device arrays; element `i` draws the bounded integer at position `i`, as the generic path does.

#### `synchronize(array: Any = None) → None`

Wait for every kernel queued on the current device.

#### `free_bytes() → int`

Free device memory plus what CuPy’s pool holds and can reuse.

The JAX backend: CPU everywhere, CUDA on Linux and Windows, Metal on macOS.

JAX runs on whatever device its installed plugins provide: `pip install "jax[cuda13]"` for NVIDIA GPUs, `jax-metal` for Apple GPUs (where available; untested in Modelly’s own runs), the CPU otherwise. JAX arrays are immutable, so every update in `modelly.gpu` is functional (`put` returns a new array).

Without `jax.config.update("jax_enable_x64", True)` JAX has no 64-bit types: floats are float32, integers int32, and the Philox products go through 16-bit halves. The integers drawn are the same either way; uniforms are float32 with 24 random bits, the same values numpy gives for `random(n, dtype=float32)`.

#### `class JaxBackend`

Arrays on JAX’s default device.

Import JAX, find its default device and jit the Philox rounds.

#### `property float_dtype: Any`

float64 with `jax_enable_x64`, else float32.

#### `property int_dtype: Any`

int64 with `jax_enable_x64`, else int32.

#### `property device: str`

The platform and kind of JAX’s default device (`cuda`, `METAL`, `cpu`).

#### `to_numpy(array: Any) → ndarray`

Copy `array` to the host.

#### `put(array: Any, index: Any, values: Any) → Any`

`array` with `array[index] = values`, as a new array.

#### `segment_add(index: Any, weights: Any, n: int) → Any`

Per-bin sums by a scatter-add; integer weights stay integers (exact).

#### `bincount(index: Any, n: int) → Any`

Occurrences of each bin by a scatter-add of ones.

#### `argsort_stable(values: Any) → Any`

A stable argsort (JAX’s keyword differs from numpy’s).

#### `philox(block: Any, words: tuple[int, int, int], key: tuple[int, int])`

The jitted Philox rounds (compiled once per shape; any key, no recompiling).

#### `synchronize(array: Any = None) → None`

Block until `array` (or every pending computation) is ready.

#### `free_bytes() → int`

Free memory of the device; available host memory on the CPU.

## Random streams

Philox4x32-10: the counter-based generator every Modelly backend draws from.

A counter-based generator maps a 128-bit counter and a 64-bit key to 128 random bits with no state in between (Salmon, Moraes, Dror and Shaw, “Parallel random numbers: as easy as 1, 2, 3”, SC 2011). Any element of any stream can therefore be computed on its own, on any device, in any order: the numbers a GPU draws for agent `i` are the numbers the CPU draws for agent `i`.

`philox4x32` here is written once against the array API (`xp` is numpy, CuPy or `jax.numpy`) and checked against the published known-answer vectors of the Random123 library. Numpy’s own `numpy.random.Philox` is the 4x64 variant, so its streams are not these. The CuPy backend runs the same rounds as CUDA kernels (`CUDA_PHILOX`), checked bit for bit against this one.

Two ways to compute the high half of a 32 x 32-bit product: in 64-bit integers (numpy, CuPy, JAX with `jax_enable_x64`), or from 16-bit halves in 32-bit integers (JAX without 64-bit types). Both give the same bits.

#### `mulhilo_wide(a: Any, b: Any, xp: Any) → tuple[Any, Any]`

High and low words of `a * b` for uint32 arrays, through 64-bit integers.

#### `mulhilo_narrow(a: Any, b: Any, xp: Any) → tuple[Any, Any]`

High and low words of `a * b` for uint32 arrays, from 16-bit halves only.

#### `philox4x32(counter: tuple[Any, Any, Any, Any], key: tuple[int, int], xp: Any, wide: bool = True) → tuple[Any, Any, Any, Any]`

The four output words of Philox4x32-10 for every counter.

**Parameters:**

- **counter** – four uint32 words; arrays broadcast against each other.
- **key** – two 32-bit integers (or two uint32 arrays, such as a traced JAX key).
- **xp** – the array namespace (numpy, CuPy or `jax.numpy`).
- **wide** – multiply through 64-bit integers; `False` for 32-bit-only JAX.

**Returns:**

Four uint32 arrays of the broadcast shape of `counter`.

#### `philox4x32_reference(counter: tuple[int, ...], key: tuple[int, int]) → tuple`

Philox4x32-10 for one counter in Python integers: the reference of the others.

Random streams keyed by (seed, stream) that give the same numbers on every backend.

A [`PhiloxStream`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.streams.PhiloxStream) holds no generator state, only a count of the draws made so far. Draw number `call` of stream `stream` gives element `i` the Philox4x32-10 block at counter `(i // k, sub, call, stream)` and key `seed`, where `k` elements share one 128-bit block. So the numbers depend on the element’s position only, not on the device, the batch it is drawn in or the order of evaluation:

```default
stream = PhiloxStream(seed=42, stream=0, backend="cupy")
alive = stream.bernoulli(survival)              # one draw per element
draws = stream.draws()                          # one draw, in batches
first, rest = draws.random(1000), draws.random(500, start=1000)
```

Uniforms are float64 with 53 random bits (two words, as numpy builds them) or float32 with 24 (one word); bounded integers are `high * word >> 32`, which is exact and the same on every backend, with a bias below `high / 2**32`. Limits per draw: `2**32` blocks, so about 8.6 billion float64 uniforms.

#### `class PhiloxDraw(stream: PhiloxStream, call: int)`

One draw of a stream: elements addressed by position, drawable in batches.

Bind the stream and this draw’s number.

#### `property backend: Backend`

The stream’s backend.

#### `words(n: int, start: int = 0, per_element: int = 1, sub: int = 0)`

`per_element` uint32 words for each of `n` elements from `start`: (n, k).

#### `words_at(positions: Any, per_element: int = 1, sub: int = 0)`

The words `words` gives the elements at `positions` (any order): (n, k).

#### `bits(n: int, start: int = 0, sub: int = 0)`

`n` uniform uint32 words.

#### `random(n: int, start: int = 0, dtype: Any = None, sub: int = 0)`

`n` uniforms in [0, 1); float64 unless `dtype` or the backend says float32.

#### `random_at(positions: Any, dtype: Any = None, sub: int = 0)`

The uniforms `random` gives the elements at `positions`.

#### `integers(high: Any, n: int | None = None, start: int = 0, sub: int = 0)`

Integers in `[0, high)`, `high` a scalar or one bound per element (< 2**32).

#### `binomial(count: Any, p: Any, start: int = 0)`

One Binomial(count, p) variate per element (see `modelly.gpu.binomial`).

#### `class PhiloxStream(seed: int, stream: int = 0, backend: Any = None)`

Counter-based random numbers for one (seed, stream) pair, on one backend.

**Parameters:**

- **seed** – a non-negative integer below 2**64, the Philox key.
- **stream** – the stream number below 2**32; streams of one seed are independent.
- **backend** – a backend or backend name (see `get_backend`).

Key the stream; no number is drawn yet.

#### `draws() → PhiloxDraw`

The next draw, for drawing one quantity in batches or by position.

#### `random(n: int, dtype: Any = None)`

`n` uniforms in [0, 1).

#### `integers(high: Any, n: int | None = None)`

Integers in `[0, high)`, one per element of `high` (or `n` of them).

#### `bernoulli(p: Any, n: int | None = None)`

`n` (or one per element of `p`) booleans, True with probability `p`.

#### `binomial(count: Any, p: Any)`

One Binomial(count, p) variate per element of `count`.

#### `spawn(stream: int) → PhiloxStream`

Stream `stream` of the same seed and backend, at its first draw.

Binomial variates from a Philox draw, the same on every backend for the same draw.

Two exact samplers, chosen per element by the mean `m = count * min(p, 1 - p)`:

- `m < 10`: inversion. One uniform `u`; walk the cumulative probabilities from `P(0) = (1 - p) ** count` (by repeated squaring, multiplications only) with the ratio `P(k) / P(k - 1)` until they pass `u`. The walk stops at `m + 10 * sqrt(m (1 - p) + 1)`, beyond which the remaining mass is below 1e-20 (the bound numpy uses before it restarts).
- `m >= 10`: BTRS, the transformed rejection with squeeze of Hörmann (1993, “The generation of binomial random variates”, J. Stat. Comput. Simul. 46), the algorithm of `jax.random.binomial` and TensorFlow. Rounds draw two uniforms for every element still pending; about nine in ten accept at each.

`p > 1/2` draws `count - Binomial(count, 1 - p)`. Element `i` uses the uniforms at position `start + i` of sub-streams `0` (inversion) and `2r + 1`, `2r + 2` (round `r` of BTRS), so a batch, a subset or another device gets the same variates. Only IEEE-exact operations (`+ - * /`, `sqrt`, comparisons) decide the inversion; BTRS takes logarithms, whose last bit may differ between numpy, CUDA and XLA. A different last bit changes an outcome only when a uniform falls within one rounding error of the acceptance bound, so the results are the same in practice and the same law always.

#### `binomial(draw: PhiloxDraw, count: Any, p: Any, start: int = 0) → Any`

One Binomial(count[i], p[i]) variate per element; `p` may be a scalar.

## Tables and cell spaces

Agent columns on a device: the array side of a `ColumnTable`, on a GPU.

A [`DeviceTable`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.table.DeviceTable) holds one device array per column and a [`PhiloxStream`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.streams.PhiloxStream). A step phase reads columns as arrays and assigns new ones; assignment replaces the column (JAX arrays cannot be written in place), so a phase is written functionally:

```default
people = DeviceTable.from_columns(model.columns[Person], stream)
infected = people.state == I
exposure = index.counts(people.row, infected)[people.row]
catches = (people.state == S) & people.draw(escape_probability[exposure])
people.state = xp.where(catches, I, people.state)
people.write_to(model.columns[Person])   # back to the agents, when needed
```

The same code runs on numpy, CuPy and JAX; with the same seed and stream it draws the same numbers on each. The population is fixed while the columns are on the device: add and remove agents on the host table, then copy again.

#### `class DeviceTable(stream: PhiloxStream, **columns: Any)`

Equal-length device columns and the stream their phases draw from.

**Parameters:**

- **stream** – the PhiloxStream of the table; its backend holds the columns.
- **columns** – column names and their initial values (host or device arrays).

Copy every column to the stream’s backend; they must have one length.

#### `classmethod from_columns(table: ColumnTable, stream: PhiloxStream, names: list[str] | None = None) → DeviceTable`

The live rows of a host `ColumnTable` (every column, or `names`).

#### `property backend: Backend`

The backend the columns live on.

#### `property xp: Any`

The backend’s array namespace.

#### `property columns: list[str]`

The column names.

#### `draw(p: Any) → Any`

One Bernoulli(p) per row, `p` a probability or one per row.

#### `set_where(name: str, mask: Any, value: Any) → None`

`column[mask] = value`, functionally.

#### `thin(name: str, survival: Any) → Any`

Replace the counts in `name` by Binomial(count, survival); returns them.

#### `to_numpy(name: str) → Any`

A host copy of column `name`.

#### `to_dataframe() → DataFrame`

A host copy of every column, indexed by `unique_id` when it is one.

#### `write_to(table: ColumnTable, names: list[str] | None = None) → None`

Copy columns back into the live rows of a host `ColumnTable` (same rows).

`CohortTable` on a device: binomial thinning, splits and merges as array programs.

[`DeviceCohortTable`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.cohorts.DeviceCohortTable) has the operations of [`CohortTable`](https://remipelloux.github.io/Modelly/apis/batch.html#modelly.batch.cohorts.CohortTable) (`add`, `thin`, `draw`, `split`, `compact`, `merge`, `total`, `totals_by`) with the columns on a backend and the binomial draws from a [`PhiloxStream`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.streams.PhiloxStream), so the same seed gives the same counts on numpy, CuPy and JAX. Updates are functional: `table["age"] = ...` replaces the column, and `table["stage"][rows] = x` (which works on the host table) is written `table.set_where("stage", mask, x)`.

The law of every operation is the host table’s (`docs/vectorised_phases.md`, cohort compression); the numbers differ from the host table’s, which draws from `model.rng`.

#### `class DeviceCohortTable(stream: PhiloxStream, **columns: Any)`

Rows of (state columns, count) on a device.

**Parameters:**

- **stream** – the PhiloxStream the binomial draws come from; its backend holds the rows.
- **columns** – state column names and their dtypes.

An empty table with an integer `count` and the given state columns.

#### `classmethod from_table(table: CohortTable, stream: PhiloxStream) → DeviceCohortTable`

A copy of the live rows of a host `CohortTable`.

#### `property backend: Backend`

The backend the rows live on.

#### `property columns: list[str]`

`count` then the state columns.

#### `set_where(name: str, mask: Any, value: Any) → None`

`column[mask] = value`, functionally.

#### `total(where: Any = None) → int`

Individuals in the table, or in the rows selected by the mask `where`.

#### `totals_by(column: str, minlength: int = 0) → Any`

Individuals per value of an integer state column (a device array).

#### `add(count: Any, **values: Any) → Any`

Append cohorts (scalars or equal-length arrays); returns their row indices.

#### `thin(survival: Any) → Any`

Each count becomes Binomial(count, survival); returns the new counts.

#### `draw(p: Any, where: Any = None) → Any`

Binomial(count, p) events per row (or per selected row); counts unchanged.

#### `split(p: Any, where: Any = None, **changes: Any) → Any`

Move Binomial(count, p) individuals of each selected row to a new row.

The new rows copy their source row’s state, then apply `changes`. Returns the new rows’ indices.

#### `compact() → int`

Drop the empty cohorts, keeping row order; returns how many were dropped.

#### `merge() → int`

Combine rows with identical state, summing counts; sorted by state, no empties.

#### `to_dataframe() → DataFrame`

A host copy of the rows.

A `CellIndex` on the device: per-cell counts, neighbour sums and random moves.

`DeviceCellIndex(index, backend)` copies the CSR adjacency of a [`CellIndex`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.cells.index.CellIndex) (the cells’ `connections`, in their order) to the device once. Its three operations answer the same questions as the host index, as array programs:

- `counts(rows, weights)`: agents (or a quantity) per cell, a scatter-add;
- `neighbor_sum(values)`: per cell, the sum over its neighbours, a gather and a segmented sum along the CSR rows;
- `random_neighbor(rows, stream)`: a uniformly chosen neighbour per agent, with a bounded integer from a [`PhiloxStream`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.streams.PhiloxStream).

Integer counts and sums are exact, so they are identical on every backend. Float sums are exact up to the order of additions: within a few ulps.

#### `class DeviceCellIndex(index: CellIndex, backend: Any = None)`

The adjacency of a cell space as device arrays.

**Parameters:**

- **index** – the host `CellIndex` whose adjacency is copied.
- **backend** – a backend or backend name (see `get_backend`).

Copy the CSR adjacency (row pointers and neighbour rows) to the device.

#### `classmethod from_csr(indptr: ndarray, indices: ndarray, backend: Any = None) → DeviceCellIndex`

An index from CSR arrays directly (row pointers, then neighbour rows).

#### `counts(rows: Any, weights: Any = None) → Any`

Per-cell total of `weights` (or of ones) over the agents in `rows`.

#### `neighbor_sum(values: Any) → Any`

For every cell, the sum of `values` over its neighbouring cells.

#### `random_neighbor(rows: Any, stream: PhiloxStream | PhiloxDraw) → Any`

One uniformly chosen neighbour row per entry of `rows` (from `stream`).

A row without neighbours is returned unchanged. `stream` is a `PhiloxStream` (its next draw is used) or one `PhiloxDraw`.

#### `to_layer(values: Any) → Any`

Reshape a per-cell vector to the grid’s dimensions.

## Memory

Populations larger than the GPU’s memory: plan batches and run a phase over them.

The columns stay on the host (numpy, or memory-mapped files); a phase runs on the device one batch of rows at a time. [`plan_memory()`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.memory.plan_memory) sizes the batches from the bytes a row needs on the device (its columns plus the temporaries the phase makes) and the device’s free memory; [`run_batched()`](https://remipelloux.github.io/Modelly/apis/gpu.html#modelly.gpu.memory.run_batched) copies each batch in, runs the phase and copies its outputs back:

```default
plan = plan_memory(len(state), bytes_per_row=64, backend=backend)
draw = stream.draws()                       # one draw for the whole phase

def recover(batch, start):
    u = draw.random(len(batch["days"]), start=start)
    return {"state": xp.where(u < gamma, R, batch["state"])}

out = run_batched(plan, recover, {"state": state, "days": days}, backend)
```

A phase that draws by position (`start`) gives the same numbers whatever the batch size, so a batched run equals the run in one batch, bit for bit. Only phases whose rows do not read each other batch exactly; a reduction over rows (counts per cell) is a sum of per-batch reductions, which the caller adds.

#### `class MemoryPlan(rows: int, batch_rows: int, bytes_per_row: int, budget: int)`

How many rows go to the device at once.

**Variables:**

- **rows** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – rows of the population.
- **batch_rows** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – rows per batch (the last batch may be shorter).
- **bytes_per_row** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – device bytes one row needs during the phase.
- **budget** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – device bytes the plan allows.

#### `property batches: int`

The number of batches.

#### `slices() → Iterator[slice]`

The row range of each batch, in order.

#### `plan_memory(rows: int, bytes_per_row: int, backend: Any = None, budget: int | None = None) → MemoryPlan`

Batches of rows that fit in `budget` bytes (half the free device memory by default).

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – when `bytes_per_row` is not positive.

#### `run_batched(plan: MemoryPlan, phase: Callable[[dict[str, Any], int], Mapping[str, Any]], columns: Mapping[str, ndarray], backend: Backend | str | None = None) → dict[str, ndarray]`

Run `phase(batch, start)` over the batches of `plan`; host outputs, joined.

`batch` maps each column name to the batch’s rows on the device, and `start` is the batch’s first row, for drawing by position. The phase returns device arrays, one value per row of the batch.
