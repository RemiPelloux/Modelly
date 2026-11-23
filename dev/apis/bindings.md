# Bindings for R and Julia

`modelly.bindings` holds the plain functions the R package (`r/modelly`) and the Julia package (`julia/Modelly.jl`) call. How to use them is in [From R and Julia](https://remipelloux.github.io/Modelly/dev/r_and_julia.html).

Modelly for other languages: a few functions of plain values that return data frames.

The R package (`r/modelly`, through reticulate) and the Julia package (`julia/Modelly.jl`, through PythonCall) call these functions rather than Modelly’s classes, so what crosses the language boundary is numbers, strings, lists, dictionaries and pandas DataFrames, which both bridges convert to native data frames. A model is named by a target, `path/to/model.py:Class` or `package.module:Class`.

R has no integer literal without `L`, so every count, seed and step number is converted with `int()` here, and a model parameter whose scenario field is annotated `int` is too: `modelly_run("sir.py:Epidemic", population = 1000)` works from R as written.

#### `calibrate(target: str, priors: Mapping[str, Any], observed: Mapping[str, Sequence[float]], *, steps: int, particles: int = 100, generations: int = 6, seed: int = 0, fixed: Mapping[str, Any] | None = None, executor: str = 'serial') → dict[str, DataFrame]`

ABC-SMC: the posterior summary, its particles and the trace of the generations.

`observed` maps a model reporter to its observed series, one value per step after the first. Runs are serial by default, since a language embedding Python has no script for worker processes to re-import.

#### `column(built: Any, agent_class: str, name: str) → Any`

The numpy array of column `name` of `agent_class` (by class name), not a copy.

Julia wraps it without copying (`PyArray`): writing to it writes the agents’ column. The view is valid until agents of that class are added or removed.

#### `model(target: str, params: Mapping[str, Any] | None = None, seed: int = 0) → Any`

A built model (a Python object; its methods are callable from R and Julia).

#### `parameters(target: str) → DataFrame`

The model’s scenario parameters: name, type and default, one row each.

#### `prior(spec: Any) → Prior`

A prior from `Prior` itself or `[kind, a, b]` (`["uniform", 0.05, 1]`).

#### `simulate(target: str, params: Mapping[str, Any] | None = None, seed: int = 0, steps: int = 100) → DataFrame`

One run of `steps` steps: the model reporters per step, with a `step` column.
