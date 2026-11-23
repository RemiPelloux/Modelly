# Design review: calibration (E1)

**Scope:** priors, targets, distances, the posterior object, the methods and how they run.
**Code:** `modelly.calibrate`. **Guide:** [Calibration](../calibration.md).

## Decisions

| Question | Decision | Alternatives considered | Why |
|---|---|---|---|
| What is calibrated | Scenario parameters, named as in the model's `Scenario`; other parameters fixed with `fixed=` | Free-form parameter functions; attributes set after construction | A scenario is already typed and validated, and it is what `modelly run`, experiments and manifests record, so a fitted point can be rerun and cited as is |
| Priors | One `Prior` class with named constructors (`uniform`, `log_uniform`, `normal`, `log_normal`, `truncated_normal`, `choice`) evaluated through `scipy.stats` | Accept any `scipy.stats` frozen distribution; a probabilistic-programming library | A closed set has known bounds (for the optimisers' box and the plots) and pickles in checkpoints; scipy is already a dependency, a PPL is not |
| Targets | `Target(name, observed, distance, weight, summary, output)`: an output the model records every step, the observed series or statistics, and how far apart they are | Distances on whole `DataCollector` frames; one global summary function | Reading outputs exactly as experiments do reuses the executors and the results store; per-target summaries and weights express pattern-oriented modelling (several patterns at once) |
| Distances | A function `(simulated, observed) -> float`; built-ins `rmse`, `mae`, `euclidean`, `wasserstein`, `weighted(...)` | Only RMSE; a distance object hierarchy | A plain function is the smallest contract; replicates are averaged before the distance so stochastic noise does not inflate it |
| Posterior | Weighted samples (`Posterior`): `summary` (mean, median, sd, HDI), `to_dataframe`, `best`, `predict`, `plot` | Return raw arrays; return ArviZ `InferenceData` | One small object covers every method (ABC returns many weighted samples, optimisers one); ArviZ would be a heavy dependency for a table and a plot |
| Methods | ABC rejection, ABC-SMC with an adaptive tolerance (quantile of the last distances), simulated method of moments, a built-in Gaussian-process Bayesian optimiser, and from 1.4 an adapter to outside optimisers (`ExternalBayesOpt`, optuna built in) | pyABC or ELFI as the engine; only one method | ABC needs no likelihood, which ABMs rarely have; SMC is the standard efficient variant; moments suit economists' practice; a GP search covers expensive models without an extra install, and the adapter covers the cases where a dedicated library does better |
| Reproducibility | Every random draw comes from a named stream of the seed (`Stream.PROPOSAL`, `DESIGN`, ...); a batch's runs use the seeds of the batch | One generator advanced through the run | Named streams make the posterior identical on every executor, with the compiled or the pure-Python core, and after a resume |
| Running | Batches of runs through the experiment executors, written to a Parquet store; a rerun into the same store reads finished runs | Calling the model in a loop in-process | Parallel and cluster execution, failure handling and resumption come for free, and the same store answers later questions |
| Checkpoints | `save` / `load` pickle the whole calibration with a magic header | A JSON state file | The state includes priors, kernels and generations; pickling is the only complete form, and the header refuses foreign files |

## What 1.4 added

- `ExternalBayesOpt` (optional `calibrate` extra): an outside optimiser behind `ask()` and
  `tell(point, value)` over the same unit box and common random numbers as `BayesOpt`. optuna
  is the built-in backend because it installs from pure-Python wheels on all three platforms
  and has a stable ask-and-tell API; scikit-optimize fits the same interface but is no longer
  actively released, so it is documented as a user-supplied factory instead of a built-in.
- A zoo model calibrated end to end: ABC-SMC recovers both Bass diffusion parameters inside
  their 95 % intervals on three seeds (`tests/calibrate/test_zoo_end_to_end.py`).

## Known limits

- ABC's posterior is approximate: its width depends on the final tolerance, which the trace
  reports; it is not a likelihood-based posterior.
- The optimisers return the best point, not an uncertainty.
- Gradient-based calibration needs differentiable models (1.4 F3, not part of this review).
