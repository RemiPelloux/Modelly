# Guides

One page per task, for when you already have a model and want to do something with it: check it, structure it, or run a study on it. Each guide opens with the one call that does the job, then covers the options.

## Build and check a model

- [Checking a model](https://remipelloux.github.io/Modelly/dev/lint.html) 
 `python -m modelly.lint` finds results that are wrong or cannot be reproduced from their seed, and steps that cost more than they should.
- [Profiling a model](https://remipelloux.github.io/Modelly/dev/profile.html) 
 where each step’s time goes, by `AgentSet` loop, agent class and method.
- [Checkpoints](https://remipelloux.github.io/Modelly/dev/checkpoints.html) 
 save a whole model to one file, random generators included, and resume it exactly.
- [Time travel](https://remipelloux.github.io/Modelly/dev/timetravel.html) 
 get a stochastic run back at any step without rerunning it, and diff two runs.
- [Figures and animations](https://remipelloux.github.io/Modelly/dev/figures.html) 
 journal styles, colour-blind-safe palettes and animations, from a run to a figure in a paper.
- [Studio](https://remipelloux.github.io/Modelly/dev/studio.html) 
 run one model in the browser, change its parameters and scrub back through the run.
- [In the browser](https://remipelloux.github.io/Modelly/dev/browser.html) 
 `modelly export-web` turns a model into a static page that runs with no Python on the reader’s machine.
- [Plugins](https://remipelloux.github.io/Modelly/dev/plugins.html) 
 add spaces, executors, samplers, collectors, Studio views and lint rules from a separate package.
- [Installing on a locked-down Windows machine](https://remipelloux.github.io/Modelly/dev/windows_no_admin.html) 
 no administrator rights, a proxy, or no internet access at all.
- [Event ordering](https://remipelloux.github.io/Modelly/dev/event_ordering.html) 
 what runs first when several events are due at the same time.
- [Accessibility and languages](https://remipelloux.github.io/Modelly/dev/accessibility.html) 
 Studio and the docs checked against WCAG 2.2 AA; Studio in French, Spanish, Portuguese and Chinese.

## Structure a model

- [Geospatial models](https://remipelloux.github.io/Modelly/dev/geospatial.html) 
 start from real maps: census zones, land-cover rasters and routable street networks.
- [Synthetic populations](https://remipelloux.github.io/Modelly/dev/population.html) 
 people and households drawn from aggregate census tables.
- [Networks](https://remipelloux.github.io/Modelly/dev/networks.html) 
 contact structures that change over time and have several layers at once.
- [Coupling fields and ODEs](https://remipelloux.github.io/Modelly/dev/coupling.html) 
 join agents to diffusing fields, ODEs and stock-flow models, each on its own clock.
- [ODEs in every agent](https://remipelloux.github.io/Modelly/dev/agent_odes.html) 
 one ODE per agent, integrated as one batch with each agent’s own `solve_ivp` steps, and events.
- [Language-model agents](https://remipelloux.github.io/Modelly/dev/llm_agents.html) 
 agents that decide through a language model, with schema-checked, cached, reproducible calls.
- [Differentiable models](https://remipelloux.github.io/Modelly/dev/differentiable.html) 
 gradients of a model’s outputs with respect to its parameters, through JAX.

## Run a study

- [Experiments and sweeps](https://remipelloux.github.io/Modelly/dev/experiments.html) 
 a study in one object, run on this machine, on a Dask or Ray cluster, or as a batch job.
- [Calibration](https://remipelloux.github.io/Modelly/dev/calibration.html) 
 fit parameters to observed data and say how sure the fit is.
- [Sensitivity analysis](https://remipelloux.github.io/Modelly/dev/sensitivity.html) 
 screen many parameters cheaply, then split an output’s variance between the few that matter.
- [Emulators](https://remipelloux.github.io/Modelly/dev/emulators.html) 
 a fast statistical stand-in for a slow model, with active learning and history matching.
- [Decisions](https://remipelloux.github.io/Modelly/dev/decide.html) 
 compare strategies with paired intervals, cost them, and test them across many futures.
- [Causes and explanations](https://remipelloux.github.io/Modelly/dev/explain.html) 
 treatment effects on common random numbers, the agents an outcome hangs on, counterfactuals, Shapley values.
- [Live data and assimilation](https://remipelloux.github.io/Modelly/dev/assimilation.html) 
 correct a running model as new data arrives, and forecast from the corrected state.
- [Reproducible studies](https://remipelloux.github.io/Modelly/dev/provenance.html) 
 from one run on your machine to an archive a reviewer reruns with a single command.
- [Model cards](https://remipelloux.github.io/Modelly/dev/model_cards.html) 
 what a model is for, how it was validated and where it must not be used, checked against its code.
- [The model hub](https://remipelloux.github.io/Modelly/dev/hub.html) 
 publish a model with a DOI; find, install and cite other people’s with one command.
