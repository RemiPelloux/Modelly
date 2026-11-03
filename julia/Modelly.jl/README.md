# Modelly.jl

Run, inspect and calibrate [Modelly](https://github.com/RemiPelloux/Modelly) agent-based
models from Julia, through [PythonCall](https://juliapy.github.io/PythonCall.jl/). Results are
`DataFrame`s; agent columns are arrays that share memory with the model.

```julia
using Pkg; Pkg.add(url = "https://github.com/RemiPelloux/Modelly", subdir = "julia/Modelly.jl")
using Modelly

target = Modelly.tutorial() * ":Epidemic"          # the SIR model of the tutorial
run = simulate(target; seed = 99, steps = 40, beta = 0.4)
fit = calibrate(target; priors = (beta = prior_uniform(0.05, 1.0), gamma = prior_uniform(0.02, 0.5)),
                observed = (infected = run.infected[2:end],), steps = 40, seed = 2027)
fit.summary

m = model("modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"; seed = 1)
wealth = column(m, "MoneyAgent", "wealth")          # no copy
```

The first `using Modelly` installs Python and modelly-abm through CondaPkg. To use an
environment you already have, set `JULIA_CONDAPKG_BACKEND=Null` and
`JULIA_PYTHONCALL_EXE=/path/to/python` first. The guide is
[From R and Julia](https://remipelloux.github.io/Modelly/dev/r_and_julia.html).
