# From R and Julia

Modelly writes its results as Parquet files, an open columnar format that R, Julia, DuckDB,
Spark and most data tools read directly, and it can be driven from R through
[reticulate](https://rstudio.github.io/reticulate/) and from Julia through
[PythonCall](https://juliapy.github.io/PythonCall.jl/). This page shows both directions: the
results in R or Julia, and a model run from R or Julia.

The Python snippets on this page run in Modelly's test suite (`tests/test_r_julia_guide.py`),
which also runs the SQL of the R and Julia snippets through DuckDB's Python package and makes
the same calls into Modelly that the reticulate and PythonCall snippets make. The R and Julia
code itself is not run in CI.

## Writing the results

In Python, with `pip install "modelly-abm[experiments]"` (pyarrow and DuckDB):

```python
from pathlib import Path

import duckdb

from modelly.examples.basic.boltzmann_wealth_model.model import BoltzmannWealth
from modelly.experiments import Experiment, ScenarioSpace, designs

# One run: the DataCollector's model and agent reporters, one Parquet file each.
model = BoltzmannWealth()
for _ in range(20):
    model.step()
model.datacollector.to_parquet("out/model.parquet")  # time, Gini
model.datacollector.to_parquet(
    "out/agents.parquet", kind="agent"
)  # Step, AgentID, Wealth

# A sweep: one Parquet file per run, with its parameters, seed and step on every row.
experiment = Experiment(
    model=BoltzmannWealth,
    space=ScenarioSpace(n=(50, 100), width=10, height=10),
    design=designs.latin_hypercube(4),
    replicates=2,
    steps=10,
    outputs=["gini"],
    store="runs/boltzmann",
    seed=42,
)
experiment.run(executor="serial")

# Optionally, one DuckDB database file holding every run as a table.
Path("results.duckdb").unlink(missing_ok=True)
with duckdb.connect("results.duckdb") as con:
    con.sql(
        "CREATE TABLE runs AS SELECT * FROM read_parquet('runs/boltzmann/run-*.parquet')"
    )
```

Each run file of the store has the columns `run_id`, `point`, `replicate`, `seed`, the
scenario parameters (`n`, `width`, `height`), `step` and the outputs (`gini`); see
[Experiments and sweeps](experiments.md). Parquet is the format to share: any reader of any
version opens it. A DuckDB database file is opened only by a DuckDB of a compatible storage
version, so use the same DuckDB release in Python and in R or Julia, or share the Parquet files.

## Reading the results in R

The [arrow](https://arrow.apache.org/docs/r/) package reads one file into a data frame; the
[duckdb](https://duckdb.org/docs/api/r) package queries many files with SQL without loading
them first.

```r
library(arrow)
model <- read_parquet("out/model.parquet")
agents <- read_parquet("out/agents.parquet")
summary(model$Gini)

library(DBI)
con <- dbConnect(duckdb::duckdb())
dbGetQuery(con, "SELECT n, avg(gini) AS gini FROM read_parquet('runs/boltzmann/run-*.parquet') WHERE step = 10 GROUP BY n ORDER BY n")
dbDisconnect(con, shutdown = TRUE)

# The database file written above
con <- dbConnect(duckdb::duckdb(), dbdir = "results.duckdb", read_only = TRUE)
dbGetQuery(con, "SELECT replicate, count(*) AS rows FROM runs GROUP BY replicate ORDER BY replicate")
dbDisconnect(con, shutdown = TRUE)
```

`arrow::open_dataset("runs/boltzmann")` with dplyr verbs is the other way to work on a whole
store lazily.

## Reading the results in Julia

[Parquet2.jl](https://expandingman.gitlab.io/Parquet2.jl/) reads a file as a Tables.jl table;
[DuckDB.jl](https://duckdb.org/docs/api/julia) queries many with SQL.

```julia
using DataFrames, Parquet2
model = DataFrame(Parquet2.Dataset("out/model.parquet"))
agents = DataFrame(Parquet2.Dataset("out/agents.parquet"))

using DuckDB
con = DBInterface.connect(DuckDB.DB)
gini = DataFrame(DBInterface.execute(con, "SELECT n, avg(gini) AS gini FROM read_parquet('runs/boltzmann/run-*.parquet') WHERE step = 10 GROUP BY n ORDER BY n"))
DBInterface.close!(con)

con = DBInterface.connect(DuckDB.DB, "results.duckdb")
rows = DataFrame(DBInterface.execute(con, "SELECT replicate, count(*) AS rows FROM runs GROUP BY replicate ORDER BY replicate"))
DBInterface.close!(con)
```

## Gridded results: netCDF

A model that records a grid every step (a property layer, a heat map) exports it as an
`xarray.Dataset` with a `time` dimension (`pip install "modelly-abm[xarray]"`), which xarray
writes as netCDF, the format of gridded data in climate and ecology:

```python
import numpy as np

from modelly import DataCollector, Model


class Warming(Model):
    """A 4 x 4 grid that warms at random each step."""

    def __init__(self):
        super().__init__(rng=1)
        self.heat = np.zeros((4, 4))
        self.datacollector = DataCollector(model_reporters={"heat": "heat"})

    def step(self):
        self.heat = self.heat + self.rng.random((4, 4))
        self.datacollector.collect(self)


model = Warming()
model.run_for(3)
grid = model.datacollector.to_xarray(dims={"heat": ("x", "y")})  # heat: (time, x, y)
grid.to_netcdf("out/heat.nc")
```

R reads it with `stars::read_ncdf("out/heat.nc")` or `ncdf4::nc_open("out/heat.nc")`; Julia
with `NCDatasets.NCDataset("out/heat.nc")["heat"]`.

## The R package

The `modelly` R package (in `r/modelly` of the repository) runs, inspects and calibrates
Modelly models from R without writing any Python. Results come back as data frames.

```r
install.packages("reticulate")
remotes::install_github("RemiPelloux/Modelly", subdir = "r/modelly")
modelly::install_modelly()  # once: a Python environment "r-modelly" with modelly-abm

library(modelly)
target <- paste0(modelly_tutorial(), ":Epidemic")  # the SIR model of the calibration guide
modelly_parameters(target)                          # name, type and default of each
run <- modelly_run(target, beta = 0.4, gamma = 0.1, seed = 99, steps = 40)
plot(run$step, run$infected, type = "l")

fit <- modelly_calibrate(
  target,
  priors = list(beta = prior_uniform(0.05, 1), gamma = prior_uniform(0.02, 0.5)),
  observed = list(infected = run$infected[-1]),
  steps = 40, particles = 100, generations = 6, seed = 2027
)
fit        # the posterior summary: beta 0.423 (0.332 to 0.553), gamma 0.098 (0.067 to 0.139)
plot(fit)  # a histogram of each parameter's particles
fit$particles; fit$trace
```

That is the [calibration guide](calibration.md)'s SIR tutorial, end to end from R. It gives
the posterior the guide shows for Python, number for number, because the same seed drives
the same runs. Any model works as a target: `"path/to/model.py:MyModel"` or
`"package.module:MyModel"`. Scenario parameters are passed by name. Whole numbers need no
`L`: the package converts a value to an integer when the scenario field is an `int`.
`modelly_model(target, ...)` returns the model object itself, for stepping it from R
(`model$step()`).

The package is a thin layer over `modelly.bindings`, a Python module of plain functions that
the Julia package uses too. Calibration runs serially, because an R session embedding Python
has no script for worker processes to re-import. `R CMD check` passes with no note, and the
package's tests run the tutorial and check that the posterior's intervals contain the true
values. Its tests are run with R 4.5 on Linux; Windows and macOS remain for the three-OS run
of the 1.5.0 roadmap.

## Running Modelly from R (reticulate)

Install Modelly in a Python environment and point reticulate at it; every Modelly class and
function is then callable from R. R numbers are doubles: pass whole numbers with an `L`
(`42L`), because a seed or a count must be a Python `int`.

```r
library(reticulate)
use_virtualenv("~/my-study/.venv", required = TRUE)  # or use_condaenv(), use_python()

boltzmann <- import("modelly.examples.basic.boltzmann_wealth_model.model")
scenario <- boltzmann$BoltzmannScenario(rng = 42L, n = 100L)
model <- boltzmann$BoltzmannWealth(scenario = scenario)
for (i in 1:20) model$step()

gini <- model$datacollector$get_model_vars_dataframe()  # an R data.frame
plot(gini$Gini, type = "l")
model$datacollector$to_parquet("out/from_r.parquet")

# A sweep, from R
experiments <- import("modelly.experiments")
experiment <- experiments$Experiment(
  model = boltzmann$BoltzmannWealth,
  space = experiments$ScenarioSpace(n = tuple(50L, 100L), width = 10L, height = 10L),
  design = experiments$designs$latin_hypercube(4L),
  replicates = 2L, steps = 10L, outputs = list("gini"),
  store = "runs/from_r", seed = 42L
)
experiment$run(executor = "serial")
```

Your own model works the same way: `import_from_path("model", path = "my_model")` imports a
`model.py` from a folder of your project.

## The Julia package

`Modelly.jl` (in `julia/Modelly.jl` of the repository) does from Julia what the R package does
from R, on the same `modelly.bindings`, and gives agent columns as arrays without a copy:

```julia
using Pkg; Pkg.add(url = "https://github.com/RemiPelloux/Modelly", subdir = "julia/Modelly.jl")
using Modelly

target = Modelly.tutorial() * ":Epidemic"
run = simulate(target; seed = 99, steps = 40, beta = 0.4, gamma = 0.1)   # a DataFrame
fit = calibrate(target;
    priors = (beta = prior_uniform(0.05, 1.0), gamma = prior_uniform(0.02, 0.5)),
    observed = (infected = run.infected[2:end],), steps = 40, seed = 2027)
fit.summary   # beta 0.423, gamma 0.098: the posterior of Python and R

m = model("modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"; seed = 1)
wealth = column(m, "MoneyAgent", "wealth")   # shares memory with the agents
wealth[1] = 99                               # the first agent's wealth is now 99
```

Give priors as a NamedTuple or a vector of pairs: the draws follow the priors' order, so a
`Dict`, which has none, gives a valid posterior that differs from the one Python and R give
for the same seed. `column` wraps the model's numpy array with `PyArray`, so reading and
writing it costs no copy; it is valid until agents of that class are added or removed. The
first `using Modelly` installs Python and modelly-abm through CondaPkg; set
`JULIA_CONDAPKG_BACKEND=Null` and `JULIA_PYTHONCALL_EXE` to use an environment you have. Its
tests (the tutorial's posterior to the last digit, a column written without a copy) pass with
Julia 1.13 on Linux; Windows and macOS remain for the three-OS run.

## Running Modelly from Julia (PythonCall)

PythonCall manages its own Python by default; to use the environment Modelly is installed in,
set two variables before `using PythonCall`.

```julia
ENV["JULIA_CONDAPKG_BACKEND"] = "Null"
ENV["JULIA_PYTHONCALL_EXE"] = expanduser("~/my-study/.venv/bin/python")  # Windows: .venv\Scripts\python.exe
using PythonCall, DataFrames

boltzmann = pyimport("modelly.examples.basic.boltzmann_wealth_model.model")
scenario = boltzmann.BoltzmannScenario(rng=42, n=100)
model = boltzmann.BoltzmannWealth(scenario=scenario)
for _ in 1:20
    model.step()
end

gini = DataFrame(PyPandasDataFrame(model.datacollector.get_model_vars_dataframe()))
model.datacollector.to_parquet("out/from_julia.parquet")
```

Julia integers convert to Python `int` and Julia floats to Python `float`, so no suffix is
needed. Keyword arguments are written as in Python.

## Reproducibility across languages

The seed, not the language, fixes a run: the same scenario and seed give the same results
whether the model is started from Python, R or Julia, because every draw happens in Modelly's
generators. Record the seed and the Modelly version next to the results;
[Reproducible studies](provenance.md) does that for you with `modelly run` and `modelly bundle`.
