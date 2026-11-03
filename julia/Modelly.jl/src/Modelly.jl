"""
    Modelly

Run, inspect and calibrate Modelly agent-based models from Julia. Modelly runs in Python
through PythonCall; results come back as `DataFrame`s and agent columns as arrays that share
memory with the model (no copy). A model is named by a target, `"path/to/model.py:Class"`
or `"package.module:Class"`.
"""
module Modelly

using DataFrames
using PythonCall

export parameters, simulate, model, calibrate, column, tutorial
export prior_uniform, prior_log_uniform, prior_normal, prior_log_normal

const bindings = PythonCall.pynew()

function __init__()
    PythonCall.pycopy!(bindings, pyimport("modelly.bindings"))
end

frame(df::Py) = DataFrame(PyPandasDataFrame(df))

# A Python dict in the order the caller wrote: from keyword arguments, a NamedTuple, a vector
# of pairs or a Dict. The order of the priors decides the order of the draws, so a Dict
# (unordered) gives a valid but different posterior for the same seed.
function ordered(entries, value = identity)
    d = pydict()
    for (k, v) in (entries isa NamedTuple ? pairs(entries) : entries)
        d[String(k)] = value(v)
    end
    d
end
options(kwargs) = ordered(kwargs)

"""
    tutorial(file = "epidemic.py")

The path of the SIR model of the calibration tutorial, shipped with the package.
"""
tutorial(file::AbstractString = "epidemic.py") = joinpath(@__DIR__, "..", "tutorial", file)

"""
    parameters(target)

The model's scenario parameters: name, type and default, one row each.
"""
parameters(target::AbstractString) = frame(bindings.parameters(target))

"""
    simulate(target; seed = 0, steps = 100, params...)

One run: the model reporters at every step, with a `step` column.
"""
function simulate(target::AbstractString; seed::Integer = 0, steps::Integer = 100, params...)
    frame(bindings.simulate(target, options(params), seed, steps))
end

"""
    model(target; seed = 0, params...)

The built Python model; call its methods with dot syntax, `m.step()`.
"""
model(target::AbstractString; seed::Integer = 0, params...) =
    bindings.model(target, options(params), seed)

"""
    column(m, agent_class, name)

The column `name` of the agents of class `agent_class` (its name, a string), as an array
sharing memory with the model: no copy, and writing to it writes the agents' values. Valid
until agents of that class are added or removed.
"""
column(m::Py, agent_class::AbstractString, name::AbstractString) =
    PyArray(bindings.column(m, agent_class, name))

prior_uniform(low, high) = pylist(["uniform", low, high])
prior_log_uniform(low, high) = pylist(["log_uniform", low, high])
prior_normal(mean, sd) = pylist(["normal", mean, sd])
prior_log_normal(mu, sigma) = pylist(["log_normal", mu, sigma])

"""
    calibrate(target; priors, observed, steps, particles = 100, generations = 6, seed = 0,
              fixed = Dict())

ABC-SMC: a named tuple of DataFrames, `summary`, `particles` and `trace`. `priors` maps
parameter names to priors (`prior_uniform(0.05, 1)`), `observed` maps a model reporter to
its observed values, one per step after the first. Give `priors` as a NamedTuple or a
vector of pairs to keep their order, which the draws follow: then the same seed gives the
same posterior as in Python and R.
"""
function calibrate(target::AbstractString; priors, observed, steps::Integer,
                   particles::Integer = 100, generations::Integer = 6, seed::Integer = 0,
                   fixed = Dict())
    result = bindings.calibrate(
        target, ordered(priors), ordered(observed, v -> pylist(collect(Float64, v)));
        steps = steps, particles = particles, generations = generations, seed = seed,
        fixed = options(fixed),
    )
    (summary = frame(result["summary"]), particles = frame(result["particles"]),
     trace = frame(result["trace"]))
end

end
