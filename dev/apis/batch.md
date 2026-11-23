# Batch

`modelly.batch` runs many independent model runs and holds counted populations.

Module

Contents

modelly.batch.runs

run_batch, run_grid

modelly.batch.cohorts

CohortTable

## Parallel runs

Run independent model runs over processes with the results in a deterministic order: `run_batch` for any list of tasks, `run_grid` for a factorial design with one seed per run. The output is the same as the sequential loop’s, whatever the number of workers.

Run many independent model runs in parallel, results in a deterministic order.

An experiment is usually a loop over parameter combinations and replicates, each run depending only on its own parameters and seed. `run_batch` spreads those calls over processes and returns the results in task order, so the output (a CSV, a DataFrame) is identical to the sequential loop’s, row for row. `run_grid` builds the factorial design, gives every run its own seed and returns a DataFrame.

A function defined at module level in an importable file runs in workers that start clean (`forkserver`, or `spawn`). A function defined in a notebook, a lambda or a closure cannot be imported by a fresh process; on Linux its workers are forked instead and inherit it. Forking a process with threads (numpy’s BLAS pool, for one) can deadlock the child; it is rare in practice, so the warning Python raises for it is silenced for these forks, and an importable function avoids it. As with any multiprocessing code on macOS and Windows, a script that calls `run_batch` needs the usual `if __name__ == "__main__":` guard, because the workers re-import it.

#### `default_workers() → int`

`MODELLY_WORKERS` if set, else the number of CPUs, at most eight.

#### `run_batch(run: Callable[[Any], Any], tasks: Iterable[Any], workers: int | None = None) → list[Any]`

Call `run(task)` for every task; return the results in task order.

**Parameters:**

- **run** – the function computing one run’s result.
- **tasks** – one argument per run (parameters, seed, …).
- **workers** – processes to use; `None` means `default_workers()`, 1 runs inline in this process. At most one worker starts per task.

An exception raised by a run propagates, as in the sequential loop.

#### `grid_tasks(grid: Mapping[str, Sequence[Any]], replicates: int = 1, seed: int = 0) → list[dict[str, Any]]`

Every combination of `grid` times `replicates`, each with its own seed.

Seeds come from `numpy.random.SeedSequence(seed).spawn`: independent streams, the same for a given design whatever the number of workers.

#### `run_grid(run: Callable[[dict[str, Any]], Mapping[str, Any]], grid: Mapping[str, Sequence[Any]], replicates: int = 1, seed: int = 0, workers: int | None = None) → DataFrame`

Run a factorial design in parallel; one DataFrame row per run.

`run` receives a dict with the grid’s parameters, `replicate` and `seed`, and returns a mapping of outcome names to values. The row is the task followed by the outcomes, in design order.

## Cohorts

A counted population: one row per state (stage, age, sex…) with a `count`, and every per-individual draw replaced by one binomial draw per row with exactly the same law. See [Vectorised step phases](https://remipelloux.github.io/Modelly/dev/vectorised_phases.html) for the argument.

Counted populations: one row stands for every individual in the same state.

When individuals that share a state (stage, age, sex, patch…) also share every probability they face, the model does not need one object per individual. A `CohortTable` keeps one row per state with a `count`, and the per-individual draws become one binomial draw per row:

- survival with probability `s`: `Binomial(count, s)` survivors (`thin`);
- a two-way outcome with probability `p` (sex, mating, emergence): `Binomial(count, p)` rows move to the new state (`split`);
- an event each member triggers with probability `p`: `Binomial(count, p)` events (`draw`).

Each has exactly the law of the independent per-individual draws (a sum of `count` independent Bernoulli(p) variables is Binomial(count, p)), so the counts per state have the same distribution as in the individual model; see `docs/vectorised_phases.md`. The table grows by doubling and `compact` / `merge` keep it small: it holds as many rows as there are distinct states.

eggs = CohortTable(rng, stage=np.int8, age=np.int16) eggs.add(500, stage=EGG, age=0) eggs.thin(survival[eggs[“stage”]]) eggs[“age”] += 1

#### `class CohortTable(rng: Generator, *, storage: InMemory = InMemory(), **columns: Any)`

Rows of (state columns, count); every operation is one numpy call per column.

Create an empty table with an int64 `count` and the given state columns.

**Parameters:**

- **rng** – the model’s seeded numpy generator (`model.rng`).
- **storage** – where the columns live (`modelly.core.storage`); a `MemoryMapped` keeps them in files, for more rows than memory.
- **columns** – state column names and their numpy dtypes.

#### `property columns: list[str]`

`count` then the state columns.

#### `total(where: ndarray | None = None) → int`

Individuals in the table, or in the rows selected by the mask `where`.

#### `totals_by(column: str, minlength: int = 0) → ndarray`

Individuals per value of an integer state column (a weighted bincount).

#### `add(count: Any, **values: Any) → ndarray`

Append cohorts; scalars or equal-length arrays. Returns their row indices.

Unset state columns are zero. Cohorts of size zero are kept until `compact`.

#### `thin(survival: Any) → ndarray`

Each count becomes Binomial(count, survival); returns the new counts.

#### `draw(p: Any, where: ndarray | None = None) → ndarray`

Binomial(count, p) events per row (or per selected row); counts are unchanged.

#### `split(p: Any, where: ndarray | None = None, **changes: Any) → ndarray`

Move Binomial(count, p) individuals of each selected row to a new row.

The new rows copy the state of their source row, then apply `changes` (scalars or one value per selected row). The source rows keep the rest. Returns the new rows’ indices.

#### `compact() → int`

Drop the empty cohorts, keeping row order; returns how many were dropped.

#### `merge() → int`

Combine rows with identical state into one, summing counts; drops empties.

Rows come out sorted by state. Returns how many rows were removed.

#### `to_dataframe() → DataFrame`

A copy of the live rows.

#### `from_counts(rng: Generator, counts: Mapping[tuple[Any, ...], int], **columns: Any) → CohortTable`

A table from `{(state values...): count}`, the state in `columns` order.
