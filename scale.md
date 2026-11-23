# Performance and scale

How fast Modelly runs, how to make a model faster, and how to run it on more than one core without losing its results. Start with the audit to see where the time goes, then pick the step that fits your model.

- [Performance audit](https://remipelloux.github.io/Modelly/performance.html) 
 how the core data structures were measured, what changed, and what is still on the table.
- [Vectorised step phases](https://remipelloux.github.io/Modelly/vectorised_phases.html) 
 keep agents as objects and move the bulk of a step into arrays.
- [GPU arrays](https://remipelloux.github.io/Modelly/gpu.html) 
 run column phases, cohort tables and cell-space operators on a GPU with one setting, and the same random numbers.
- [From laptop to cluster](https://remipelloux.github.io/Modelly/distributed.html) 
 split one model across processes or machines, each worker holding one part of the space.
- [Determinism and platforms](https://remipelloux.github.io/Modelly/determinism.html) 
 the same model, scenario and seed give the same run on Windows, macOS and Linux.
