# Performance and scale

How fast Modelly runs, how to make a model faster, and how to run it on more than one core
without losing its results. Start with the audit to see where the time goes, then pick the
step that fits your model.

```{container} ml-hub
- [Performance audit](performance.md)\
  how the core data structures were measured, what changed, and what is still on the table.
- [Vectorised step phases](vectorised_phases.md)\
  keep agents as objects and move the bulk of a step into arrays.
- [GPU arrays](gpu.md)\
  run column phases, cohort tables and cell-space operators on a GPU with one setting, and the same random numbers.
- [From laptop to cluster](distributed.md)\
  split one model across processes or machines, each worker holding one part of the space.
- [Determinism and platforms](determinism.md)\
  the same model, scenario and seed give the same run on Windows, macOS and Linux.
```

```{toctree}
:hidden: true

Performance audit <performance>
Vectorised step phases <vectorised_phases>
GPU arrays <gpu>
From laptop to cluster <distributed>
Determinism and platforms <determinism>
```
