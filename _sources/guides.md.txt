# Guides

One page per task, for when you already have a model and want to do something with it: check
it, structure it, or run a study on it. Each guide opens with the one call that does the job,
then covers the options.

## Build and check a model

```{container} ml-hub
- [Checking a model](lint.md)\
  `python -m modelly.lint` finds results that are wrong or cannot be reproduced from their seed, and steps that cost more than they should.
- [Profiling a model](profile.md)\
  where each step's time goes, by `AgentSet` loop, agent class and method.
- [Checkpoints](checkpoints.md)\
  save a whole model to one file, random generators included, and resume it exactly.
- [Time travel](timetravel.md)\
  get a stochastic run back at any step without rerunning it, and diff two runs.
- [Figures and animations](figures.md)\
  journal styles, colour-blind-safe palettes and animations, from a run to a figure in a paper.
- [Studio](studio.md)\
  run one model in the browser, change its parameters and scrub back through the run.
- [In the browser](browser.md)\
  `modelly export-web` turns a model into a static page that runs with no Python on the reader's machine.
- [Plugins](plugins.md)\
  add spaces, executors, samplers, collectors, Studio views and lint rules from a separate package.
```

## Structure a model

```{container} ml-hub
- [Geospatial models](geospatial.md)\
  start from real maps: census zones, land-cover rasters and routable street networks.
- [Synthetic populations](population.md)\
  people and households drawn from aggregate census tables.
- [Networks](networks.md)\
  contact structures that change over time and have several layers at once.
- [Coupling fields and ODEs](coupling.md)\
  join agents to diffusing fields, ODEs and stock-flow models, each on its own clock.
- [Language-model agents](llm_agents.md)\
  agents that decide through a language model, with schema-checked, cached, reproducible calls.
- [Differentiable models](differentiable.md)\
  gradients of a model's outputs with respect to its parameters, through JAX.
```

## Run a study

```{container} ml-hub
- [Experiments and sweeps](experiments.md)\
  a study in one object, run on this machine, on a Dask or Ray cluster, or as a batch job.
- [Calibration](calibration.md)\
  fit parameters to observed data and say how sure the fit is.
- [Sensitivity analysis](sensitivity.md)\
  screen many parameters cheaply, then split an output's variance between the few that matter.
- [Emulators](emulators.md)\
  a fast statistical stand-in for a slow model, with active learning and history matching.
- [Live data and assimilation](assimilation.md)\
  correct a running model as new data arrives, and forecast from the corrected state.
- [Reproducible studies](provenance.md)\
  from one run on your machine to an archive a reviewer reruns with a single command.
```

```{toctree}
:hidden: true
:caption: Build and check a model

Checking a model <lint>
Profiling a model <profile>
Checkpoints <checkpoints>
Time travel <timetravel>
Figures and animations <figures>
Studio <studio>
In the browser <browser>
Plugins <plugins>
```

```{toctree}
:hidden: true
:caption: Structure a model

Geospatial models <geospatial>
Synthetic populations <population>
Networks <networks>
Coupling fields and ODEs <coupling>
Language-model agents <llm_agents>
Differentiable models <differentiable>
```

```{toctree}
:hidden: true
:caption: Run a study

Experiments and sweeps <experiments>
Calibration <calibration>
Sensitivity analysis <sensitivity>
Emulators <emulators>
Live data and assimilation <assimilation>
Reproducible studies <provenance>
```
