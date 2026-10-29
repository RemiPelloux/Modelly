# Design review: sensitivity analysis (E2)

**Scope:** what is analysed, the parameter space, the methods, their estimators and results.
**Code:** `modelly.sensitivity`. **Guide:** [Sensitivity analysis](../sensitivity.md).

## Decisions

| Question | Decision | Alternatives considered | Why |
|---|---|---|---|
| What is analysed | A `Study`: a Model class run through the experiment executors (an `output` reduced by a `statistic`, averaged over replicates), a plain function, or an emulator | Models only; wrap SALib | One interface lets the same call verify a method on an analytical function (Ishigami, Sobol G) and then run it on a model or its emulator |
| Parameter space | `ScenarioSpace`, shared with experiments and calibration; methods work in the unit cube and map points back | A space of the method's own | A study, an experiment and a calibration of the same model describe their parameters once, and integer and choice dimensions behave the same everywhere |
| Screening | One-at-a-time sweeps and Morris elementary effects (`mu*`, `sigma`) on a grid of `levels` | Only Sobol | Morris ranks a dozen parameters for a few hundred runs, which is what a modeller needs before spending thousands on variance-based indices |
| Variance-based indices | Saltelli sampling from one scrambled Sobol sequence; Jansen estimators by default (Saltelli's as an option); bootstrap confidence intervals | Monte Carlo sampling; FAST | Saltelli's design gives S1 and ST from `samples * (parameters + 2)` runs; Jansen's estimators have the lowest variance in Saltelli et al. (2010); the bootstrap needs no extra runs |
| Skewed outputs | PAWN, moment-independent, from output distributions | Only variance-based indices | Variance misleads for heavy-tailed or multimodal outputs, common in ABMs |
| Expensive models | An optional Gaussian-process emulator in place of the model (and, in 1.4, the `modelly.emulate` emulators) | Always run the model | A few hundred runs can stand for the tens of thousands Sobol needs |
| Seeds | The design, the bootstrap and the runs draw from named streams of `seed` | Global state | The same seed gives the same indices on every executor |
| Results | Result objects (`MorrisResult`, `SobolResult`, ...) with tables (`ranking()`, `indices()`), plots and export | Plain dicts | Tables export to papers; plots follow the publication styles |

## What 1.4 added

- Morris stability across seeds on zoo models: the ranking of the top parameters is the same
  for every seed on the Bass diffusion and the age-structured SEIR models
  (`tests/sensitivity/test_morris_stability.py`), the "done when" left open in 1.3.

## Known limits

- Morris with few trajectories ranks parameters whose effects are close in an order that can
  change with the seed; only clearly separated parameters are stable, which is what the test
  checks.
- Indices of a stochastic model mix parametric and run-to-run variance unless replicates are
  averaged; the guide says how many to use.
