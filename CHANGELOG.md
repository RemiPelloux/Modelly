# Changelog

All notable changes to Modelly. The format follows Keep a Changelog; versions follow semantic
versioning.

## Unreleased

### Added

- Per-agent random streams (provisional): with `agent_streams = True` on a model class,
  `agent.random` and `agent.rng` are generators of the agent's own, seeded from the model's
  seed and `Agent.stream_key()` (`unique_id` by default). An agent draws the same numbers
  whatever the activation order or the population, and checkpoints continue every stream.
  Off by default; models without the flag draw exactly as before.
- `modelly.distributed.partition` (provisional): `grid_blocks(rows, cols).layout(grid)` cuts a
  2-D grid into balanced blocks and gives each cell's owner and each block's halo, on plain
  grids and tori.
- Split runs (`modelly.distributed`, provisional): a model that declares
  `partitionable = Partitionable(space=..., phases=...)` and uses per-agent streams is built
  split across workers with `Cluster(backend=...).build(Model, scenario, partition)`, with ghost
  agents exchanged at partition borders before a phase that looks across them and agents
  migrating with their streams after a phase that moves them. Backends `local`, `mpi`
  (mpi4py, new `distributed` extra), `dask` and `ray` (imported only when used). Results equal
  one process for the same seed, byte for byte; a model that breaks the contract (model-level
  draws in a phase, Column agents, own events, moves into cells with a capacity, agent
  references in attributes, births keyed on `unique_id`) is refused with the reason, and
  `owns()` lets a model build only its partition's agents.
- Graph and k-d partitioners (provisional): `partition.graph(parts)` splits a `Network` by
  breadth-first banding and greedy boundary refinement, `partition.kd(parts)` a
  `ContinuousSpace` by recursive bisection at the population quantile; both deterministic,
  pure numpy, with halos by hops or by distance.
- Distributed collectors and checkpoints (provisional): `Sum`, `Min` and `Max` reporters reduced
  across partitions (`collect()`), agent `snapshot()`s in stream-key order, and
  `checkpoint(directory)` writing one file per partition plus an `index.json` with digests,
  which `Cluster.restore` continues draw for draw.
- Partition-independence check (provisional): `check_independence(Model, scenario, partitions,
  steps)` runs one process and each split and raises at the first differing reporter or agent
  state; the test suite runs it on a grid, a network and a continuous model at 1, 2, 4 and 16
  partitions, and on MPI with 2 and 4 ranks. `benchmarks/distributed/weak_scaling.py` measures
  weak scaling, with the guide "From laptop to cluster" (`docs/distributed.md`).
- `modelly.stream` (provisional): `ReplaySource`, `CSVSource` (a growing file) and
  `HTTPSource` hand out observations once each, in time order; `ObservationOperator` reads the
  same quantities from a model, with residuals and a Gaussian log-likelihood.
- `modelly.stream.Ensemble` (provisional): `n` replicates of one scenario with spawned seeds,
  advanced in lock step in this process, with starting values drawn from a `prior`; `band` and
  `forecast` give the (weighted) mean and quantiles of an operator now and ahead as a
  long-format DataFrame (`time`, `quantity`, `mean`, `q0.05`, ...), for plots and live views.
- `modelly.stream.ParticleFilter` (provisional): the bootstrap particle filter (Gordon et al.
  1993) over an ensemble, with the effective sample size tracked and systematic resampling
  (Douc & Cappé 2005) below a threshold; duplicates are checkpoint copies reseeded from derived
  keys, so a run is bit-identical for a seed with the compiled or the pure-Python core. The new
  nowcasting tutorial (`docs/assimilation.md`) tracks a synthetic truth with it.
- `modelly.stream.EnsembleKalmanFilter` (provisional): the stochastic ensemble Kalman filter
  with perturbed observations (Evensen 1994, 2003) on named model attributes
  (state/parameter augmentation), with optional bounds; deterministic for a seed.
- `modelly.stream.MQTTSource` and `KafkaSource` (provisional): sources reading JSON records from
  an MQTT or a Kafka topic, through the new optional extras `mqtt` (paho-mqtt) and `kafka`
  (confluent-kafka), or through a client passed in.
- population: `modelly.population`, synthetic populations from aggregate tables: `ipf` and
  `trs` (truncate, replicate, sample) rounding in `synthesize_population`, `marginal_errors`
  to check the fit, `anneal` (combinatorial optimisation of whole records by simulated
  annealing), `assign_households` from a household-size table, `locate_households` and
  `assign_places` (nearest school or workplace with room, within a distance limit), and
  `contact_network` (household, school and work layers of a `MultilayerNetwork`). No bundled
  personal data; `modelly.space.geo.ipf` and `synthesize_population` keep working.
- zoo: `age_seir.model.scenario_from_population` starts the age-structured SEIR model from a
  synthetic population (group sizes and contact matrix); the default scenario is unchanged.
- geo: `modelly.space.geo.samples`, small real samples of Burlington, Vermont, bundled for
  offline use with their licences in `NOTICE.md` (OpenStreetMap streets, ODbL; ESA WorldCover
  land cover, CC BY 4.0; census tracts, public domain), and `scripts/geo_data.py` to download
  the full sources, verify their SHA-256 and rebuild the samples.
- zoo: `road_traffic`, traffic assignment on the OpenStreetMap streets, validated against the
  exact edge betweenness.
- zoo: `habitat_selection`, Metropolis dispersal over the WorldCover raster, validated against
  its stationary law.
- zoo: `schelling_regions`, Schelling segregation on the census tracts by contiguity.
- `modelly.couple`: multi-scale coupling. `Field` makes a grid property layer diffuse, drift and
  decay on its own sub-steps (finite volumes, explicit with a stability check or implicit;
  closed, absorbing or periodic boundaries; mass conserved to round-off, with a budget of what
  was added, left and decayed); `ODE` and `StockFlow` integrate continuous components with
  scipy's `solve_ivp`; `Coupling` and `Phase` run them with the agents' step phases, checked at
  build time for reads with no writer, two writers and cycles inside a phase. Coupled models
  checkpoint and resume bit for bit. Guide: `docs/coupling.md`.
- Two coupled zoo models: `nutrient_foragers` (foragers on a diffusing nutrient field,
  validated against the carrying capacity of the energy balance) and `hospital_epidemic` (SIR
  agents coupled to a hospital-capacity stock-flow ODE, validated against the final-size
  relation and the hospital's exact linear solution), both with mass-balance tests.
- `modelly.emulate` emulators (provisional): `GaussianEmulator` (one Gaussian process per
  output, fitted with restarts, with covariances and conditioning) and `NeuralEmulator` (a
  numpy ensemble of small networks), fitted to unit-cube points or to an experiment's runs
  (`from_results`), and usable in place of the model in `modelly.sensitivity`; `Simulation`
  runs a model through the experiment executors (or a function) for several outputs, each
  reduced by a statistic, optionally with common random numbers. `GaussianProcess.fit` takes
  `restarts=True` and the process gains `covariance`, `condition` and `noise_variance`; the
  default fit is unchanged, bit for bit.
- `modelly.emulate.ActiveLearning` (provisional): designs that run next where the emulator is
  least certain (integrated variance reduction, or the largest variance), chosen in batches by
  conditioning on each pick, seeded and resumable. Against Latin hypercubes with the same
  emulator (`benchmarks/emulate/active_vs_lhs.py`), it saves a factor of 1.6 to 2.7
  of the runs on the zoo's Bass diffusion (2 or more at 20, 40 and 50+ runs, 1.3 at 30), but
  only 1.1 to 1.4 on Branin below 80 runs and 0.8 to 1.4 on Ishigami: the roadmap's factor of 2 holds on
  one of the two kinds of benchmark (table in `docs/emulators.md`).
- `modelly.emulate.HistoryMatch` (provisional): history matching in waves, with the
  implausibility `|z - E[f(x)]| / sqrt(Var_emulator + Var_obs + Var_discrepancy)`, a cutoff of
  3, NROY tracked on a fixed sample and emulators refitted inside it every wave. On the zoo's
  age-structured SEIR (truth at the default parameters, three outputs), four waves of 20 runs
  leave 17 %, 4.4 %, 3.1 % and 2.5 % of the box, the truth inside every time. Guide:
  `docs/emulators.md`.
- gpu: `modelly.gpu` runs column phases (`DeviceTable`), cohort tables (`DeviceCohortTable`,
  binomial thinning included) and cell-space operators (`DeviceCellIndex`: counts, neighbour
  sums, random-neighbour moves) on numpy, CuPy or JAX, chosen by `get_backend` or
  `MODELLY_BACKEND` with a numpy fallback; `PhiloxStream`, a Philox4x32-10 stream keyed by
  (seed, stream), draws the same numbers on every backend (Random123 known-answer vectors);
  `plan_memory` / `run_batched` run populations larger than the GPU in batches, bit for bit;
  `modelly-gpu` variants of the grid epidemic and insect cohorts playbooks. On a laptop
  RTX 5050 the grid epidemic at 10 million agents keeps the CPU run's integer state bit for bit
  and runs its 60 steps 34x faster than the CPU column variant (`docs/performance.md`).
  Extras `gpu` (CuPy) and `diff` (JAX); `import modelly` loads neither.
- diff: `modelly.diff` simulates column phases traced by JAX (`DiffModel`, `@phase` with a
  `differentiable` flag) and differentiates their outputs with respect to parameters:
  pathwise normal and uniform draws, Bernoulli choices through straight-through, Gumbel-softmax
  or score-function estimators (each warns `GradientApproximationWarning`), `check_gradients`
  against finite differences, and `GradientCalibration` (Adam on `modelly.calibrate` priors and
  targets, deterministic for a seed). Differentiable twins of the Bass diffusion and
  Bouchaud-Mezard zoo models recover known parameters; `docs/differentiable.md` says when the
  gradients mean something.
- quality: partition independence in the determinism suite. The three reference models of split
  runs (`grid_epidemic`, `network_sir`, `continuous_sir`) are golden examples, and
  `tests/determinism/test_determinism_partition.py` splits each from the golden seed (2, 4 and
  16 partitions) and checks every output equals the single-process run, so a split run on any
  platform gives the golden digest. A new `mpi` workflow runs the distributed tests under Open
  MPI on Ubuntu and macOS and under MS-MPI on Windows (2 ranks only); `test_mpi.py` uses
  `mpiexec` on Windows and reads the rank counts from `MODELLY_MPI_RANKS`.
- provenance: the language-model response cache travels with the study. `modelly run` exports
  the replies of the model's `modelly.llm.Client`s to `llm-responses.jsonl.gz` and records it in
  the manifest (`llm_cache`, an optional field of manifest format 1); `modelly bundle` packs it
  and refuses a run whose replies changed; `modelly verify` reruns inside the new
  `modelly.llm.replay.replaying(path)` (provisional), where every client answers from the
  recorded replies only, so a bundle verifies with no network and no API key. Runs without a
  client write the same manifest and bundle as before.
- plugins: Modelly now reads three more entry-point groups. `modelly.samplers` adds design kinds
  (`[design] kind = "name"` in an experiment file, `designs.design_factory` and `design_kinds`,
  provisional); `modelly.lint_rules` adds rules to `modelly lint` (an object with a `Rule` and a
  `check(tree)`, `modelly.lint.plugins`, provisional); `modelly.studio_views` adds Studio tabs.
  A rule or view that fails to load or reuses a built-in code is skipped with a warning. A
  complete third-party package with one entry point in every group is in
  `examples/plugins/modelly-example-plugin`, tested in `tests/test_example_plugin.py`.
- `modelly.calibrate.ExternalBayesOpt` (provisional): Bayesian optimisation by an outside
  library over the same unit box and common random numbers as `BayesOpt`, through any optimiser
  with `ask()` and `tell(point, value)`; the built-in backend is optuna (TPE seeded from the
  calibration's seed, or any optuna sampler), from the new optional extra `calibrate` and
  imported only when the search starts. Also `method = "external_bayes_opt"` in calibration
  files.
- calibrate: a zoo model calibrated end to end. ABC-SMC recovers the Bass diffusion model's
  innovation and imitation inside their 95 % intervals on three seeds, from priors ten times
  wider (`tests/calibrate/test_zoo_end_to_end.py`, "A zoo model end to end" in
  `docs/calibration.md`).
- sensitivity: Morris stability across seeds on zoo models. The whole ranking of the Bass
  diffusion model's three parameters, and the top parameter of the age-structured SEIR model,
  are the same on five seeds (`tests/sensitivity/test_morris_stability.py`); the guide says
  which parameters swap places and why.
- docs: design reviews of calibration (E1), sensitivity analysis (E2) and language-model agents
  (E7), each what was decided, what else was considered and why (`docs/design/`).
- quality: WebAssembly in the release matrix. The release workflow's new `pyodide` job installs
  the pure wheel with micropip in Pyodide under node, imports `modelly`, checks the pure-Python
  twins are in use and runs the Boltzmann wealth example (`scripts/pyodide-smoke.mjs`); the
  PyPI upload waits for it. In Pyodide `import modelly` needs Pyodide's `sqlite3` package, and
  importing any bundled example needs `networkx`.
- quality: SLURM and PBS job scripts run for real. `test_cluster_scripts.py` puts stand-in
  `sbatch` and `qsub` executables on `PATH` that run the generated job script in `bash` once per
  array element, so every element runs in a fresh shell and interpreter and must give the serial
  numbers; the new `platforms` workflow's `slurm` job submits the same array to a single-node
  SLURM cluster on the runner (`MODELLY_REAL_SCHEDULER=slurm`).
- quality: a bundle made on Linux verified on macOS and Windows. The `platforms` workflow runs
  and bundles three studies on Ubuntu (Boltzmann wealth, Schelling, and the language-model
  opinions example, whose replies travel in the bundle), and macOS and Windows jobs unpack each
  and run `modelly verify`.
- release: `.zenodo.json` at the repository root, so the GitHub-Zenodo integration archives each
  GitHub release with the same title, licence, keywords and creators as `CITATION.cff` (no
  contact data; the version comes from the tag), checked by `tests/test_zenodo.py`.

- lint: MDL011 (a scipy.stats.qmc engine, a `.rvs()` draw or a SALib sampler without a seed),
  MDL013 (a mutable default in a `Scenario`, shared by every scenario of the class) and MDL014
  (a clock, timer or OS entropy read in a calibration `Target`); `--fix` seeds a sampler in a
  model or agent method from `self.rng`. 21 rules, five with a fix.
- `modelly lint --lsp`: the linter as a language server over stdio (standard library only),
  publishing findings as diagnostics on open, change and save, with the safe fix and a
  `# noqa` comment as quick fixes; settings for Neovim, Helix, VS Code and PyCharm in
  `docs/lint.md`.
- `.pre-commit-hooks.yaml`: `modelly-lint` and `modelly-lint-fix` hooks, so a project's
  pre-commit configuration runs `modelly lint` (or its safe fixes) on the staged files.
- `modelly new --template geo` (residents of a town's districts in a `GeoSpace`) and
  `--template llm` (citizens deciding through `modelly.llm`, offline by default); both pass
  their determinism test and `modelly lint` as generated.
- `DataCollector.to_xarray` (and `modelly.data.xarray_export.to_xarray`): model reporters as an
  `xarray.Dataset` over `time`, arrays such as a grid stacked into `(time, ...)`, agent
  reporters as a `(time, AgentID)` panel; xarray is the new optional `xarray` extra.
- docs: From R and Julia, reading Modelly's Parquet, DuckDB and netCDF results with arrow,
  duckdb, Parquet2.jl and DuckDB.jl, and running Modelly from R (reticulate) and Julia
  (PythonCall); the Python side of every snippet runs in the test suite.
- `modelly netlogo` (`python -m modelly.netlogo`): translate a NetLogo model (`.nlogo`) into a
  runnable, seeded, lint-clean Modelly model for a documented subset (turtles, patches, breeds,
  `ask`, `set`, `if`/`ifelse`, `repeat`, `create-`/`hatch`/`sprout`, movement, `neighbors`,
  `one-of`, `random`, globals; sliders and switches become Scenario fields). Lines outside the
  subset stay as `# NETLOGO` comments and are listed with their line numbers. Ships Fire and
  Wolf Sheep Predation sources written from the published descriptions; the translated Fire
  model shows the percolation threshold near 59% density. See `docs/netlogo.md`.
- Strict type checking: `[tool.mypy]` in pyproject.toml runs mypy in strict mode on batch,
  bench, calibrate, dev, experiments, lint, llm, netlogo, new, profile, provenance, scenarios,
  sensitivity, timetravel, the data exports and the top-level modules (156 files); a new `types`
  stage of `scripts/ci-local.sh` and `python -m modelly.dev gate` runs it with installed mypy,
  else the pinned mypy through `uvx`, and is skipped with a message when neither is available.

- web: `modelly export-web model.py:Model --out site/` writes a static site that runs the
  model in the browser with Pyodide (pinned 314.0.7, from its CDN): Studio's parameter panel,
  run controls, a space view and a reporter plot, the model in a Web Worker, Modelly as a
  trimmed pure-Python wheel and only the packages the model imports; every example and zoo
  model runs from its export (`tests/web/test_browser.py`, CI job `browser`), and the
  gallery embeds three live models. A first visit transfers 14 MB (Pyodide, numpy, pandas)
  and is ready in 8 s on a 50 Mbit/s line, 21 s on DevTools "Fast 4G"
  (`tools/web/measure_load.py`). Guide: `docs/browser.md`.
- native: the C modules build for WebAssembly with Emscripten (`pyodide build`,
  `scripts/build-wasm-wheel.sh`); `modelly export-web --wheel` ships that wheel.

### Changed

- docs: the build fails on warnings. `scripts/build-docs-version.sh` passes `-W --keep-going` by
  default (`SPHINXOPTS=` builds an old tag that warns) and the docs workflow sets it. The build
  was made warning-free first: a docstring formula read as a substitution, ambiguous `Grid` and
  `Observation` type references from imports only made for type checking, and the "no lexer"
  warnings of the text-notebook tutorials, which appear only when they are not executed and are
  filtered in `conf.py`.

### Deprecated

- `modelly.space.geo.ipf` and `modelly.space.geo.synthesize_population` (also through
  `modelly.space.geo.population`, with its constants) warn with a `ModellyDeprecationWarning`
  and go in 2.0: import them from `modelly.population`. They are the same functions, so results
  do not change. `docs/deprecations.md` gains "Announced for 2.0", every change 2.0 makes with
  what to use today and when it starts to warn.
### Fixed

- Modelly imports and runs under Pyodide: the profiler falls back to `process_time` where
  `thread_time` is missing, the LLM client sends calls one at a time where threads cannot
  start, `synthesize_population` passes `intp` counts to `np.repeat` (32-bit numpy), and
  `modelly.examples` imports each example on first use instead of all of them.

## 1.3.3 - 2026-10-27

A codemod release: `python -m modelly.migrate` ports Mesa 3.5's own examples. The library code
the models run is 1.3.2's; only `modelly/migrate.py` and its rules changed. No score is slower
than 1.3.2 (core operations, the playbooks seed by seed, and the notebooks; see
`docs/performance.md`).

### Fixed

- migrate: `mesa.experimental.scenarios` and `mesa.experimental.data_collection` map to
  `modelly.scenarios` and `modelly.data.recorders`; dotted names such as
  `mesa.discrete_space.CellAgent` go through the module map; a Mesa module with no Modelly
  equivalent is reported instead of silently rewritten.

### Benchmarks

- `benchmarks/mesa_examples`: eight of Mesa 3.5's ten bundled examples ported by the codemod,
  timed and compared against the originals.
- Every playbook, the ports and the mesa-frames thread comparison re-measured at a fixed
  frequency: performance governor, turbo disabled, the 1.9 GHz base clock, CPU 2, ten rounds at
  `627459a`, every per-round ratio within 15% of its median. Absolute seconds are longer than
  with turbo; the ratios are the point.
- Fairer Sugarscape baselines: the Mesa 2.3 forager no longer builds a whole-grid mask with
  `select_cells` for every move (the cached neighbourhood gives the same runs, bit for bit,
  4 to 5x faster), and both Mesa versions run the same single-pass search as Modelly's cell-list
  variant. All variants re-timed in one session, ten rounds on a performance core, the order
  rotating every round: columns run the steps 4.6 to 45x faster than Mesa 2.3 (4.0 to 32x
  including construction) and 2.9 to 33x faster than Mesa 3.5, cohorts 243x (217x including
  construction) and 133x; cell lists 1.3 to 14x and 1.3 to 11x. Against Mesa 2.3, Mesa 3.5
  runs the steps 0.91x (predator-prey) to 3.1x (network) as fast, mesa-frames 0.71x (Sugarscape)
  to 6.5x (grid epidemic).
- A hand-vectorised Mesa 3.5 baseline (`mesa3np_model.py`) for the grid epidemic, Schelling and
  Boltzmann wealth: Mesa's model, grids, property layers and seeding with the population in numpy
  arrays and no agent objects. It agrees with Mesa 2.3 over 100 seeds and is faster than
  Modelly's columns (4.4x, 1.8x and 2.8x), which keep an agent per individual; the tables show it
  as its own column.
- The Mesa Boltzmann baselines compute the Gini coefficient with numpy, as Modelly's does; the
  statistics are unchanged.
- A mesa-frames variant (`frames_model.py`) of four playbooks, run in `.venv-frames` with polars on
  one thread: Modelly columns are 3.0 to 9.4x faster. With all of polars' threads mesa-frames is
  slower than on one on three of the four workloads (grid epidemic 1.73 s against 1.52 s,
  Boltzmann 2.61 s against 1.46 s, Sugarscape 4.29 s against 2.96 s) and faster only on
  Schelling (2.12 s against 2.90 s; `paper/data/frames_threads.json`). Mesa 3.5's flocking uses
  `mesa.space.ContinuousSpace`, 1.6x faster than its experimental space and bit-identical to Mesa
  2.3. Each result file records the commit, date, load, core, power policy and versions
  (`benchmarks/playbooks/environment.py`).
- `benchmarks/ports/`: the two playbooks without a Mesa 2 grid, ported from Mesa 2.3 by the
  codemod and the steps it reports, bit-identical to the originals, at 0.22 (insects) and 0.37
  (Boltzmann) of Mesa 2.3's CPU time.
- `benchmarks/ports_mesa3/`: five Mesa 3.5 playbooks ported by the codemod alone
  (`python -m modelly.migrate --write`), at 0.45 (Boltzmann), 0.51 (insects), 0.74 (grid
  epidemic), 0.86 (network) and 0.93 (Schelling) of Mesa 3.5's CPU time. Not
  bit-identical (the random streams differ); over 100 seeds 24 of 26 statistics are equivalent
  within half a standard deviation and nothing is significant after Holm. Flocking (legacy
  `ContinuousSpace`), predator-prey and Sugarscape (`PropertyLayer`) do not port this way.
  Timings and agreement in `paper/data/port_public.json`.
- The Mesa 3.5 implementations pass the 100-seed agreement study against Mesa 2.3 (all 40
  statistics equivalent within half a standard deviation).

## 1.3.2 - 2026-10-25

A correctness release: ABC-SMC importance weights near a bounded prior are now exact. No score
is slower than 1.3.1 (core operations, the playbooks seed by seed, and the notebooks; the
playbooks and the operations they time run the same Python and the same machine code as 1.3.1).

### Added

- A performance guard for contributors: `python -m modelly.dev perf` times 17 core operations
  of the working tree against the last release (built from its tag, same compiler), in paired
  alternating bursts on one core, and fails when one is significantly slower; suspects are
  re-timed before failing. `python -m modelly.dev install-hooks` makes git run it before every
  commit that touches `modelly/` (`.githooks/pre-commit`; about ten seconds).

### Fixed

- ABC-SMC importance weights near a bounded prior. A proposal that left the prior's support
  was moved again from the same ancestor, so particles close to a bound were over-weighted
  (by 17% in the bin next to the bound, for a population crowding it). The ancestor is now
  redrawn as well (Toni et al., 2009): the proposal is the mixture truncated to the support,
  and the weights are exact. Posteriors from the same seed differ from 1.3.1's; the
  calibration guide's example was rerun.

### Benchmarks

- The playbooks have a Mesa 3.5 variant (`mesa3_model.py`), written the way Mesa 3.5's API and
  examples intend, checked to agree with the Mesa 2.3 reference in distribution. All variants
  were re-timed in one session, five rounds each: columns run the steps 4.9 to 60x faster than
  Mesa 2.3 and 2.6 to 37x faster than Mesa 3.5, cohorts 249x and 136x.

### Documentation

- The same-code comparison with Mesa 2.3 is corrected: the "12% faster" figure paired the
  Mesa notebook with an optimised Modelly notebook. The plain codemod port runs at 0.94 of
  Mesa's time with `FastRandom` and 1.02 to 1.04 with `random.Random`, bit-identical output
  (`docs/performance.md`, README, documentation home page).

## 1.3.1 - 2026-10-24

No score is slower than 1.2.0 any more: benchmarked against the 1.2.0 wheel with identical
dependencies (core operations, the playbooks and a research notebook, in paired alternating
runs; `docs/performance.md`, "No regression from release to release").

### Performance

- Reading a `Column` attribute costs what it did in 1.2.0 again. 1.3.0's getter kept the
  column's name for the error of a removed agent, which cost about 2.5% per read; it now looks
  the name up only when the error is raised. The error is unchanged.
- On regular (GIL) builds, the neighbourhood walk (`Cell.get_neighborhood`) and the cell move
  are 1.2.0's code again, without the free-threading safety 1.3.0 added to every call (a
  reference count per neighbour, a cache-generation check per move). Free-threaded builds
  keep their safe paths.
- `FixedAgent.remove` reads its cell once.

### Fixed

- A timing test of `modelly profile --sizes` compares populations 16 times apart, so it no
  longer fails on a slow runner.

## 1.3.0 - 2026-10-24

The research release: calibrate, explain, scale and publish a model, on Windows, macOS and
Linux. Everything from 1.2 keeps working; what 2.0 will change now warns (see
`docs/deprecations.md`). The plan behind it is in `docs/roadmap/1.3.0.md`.

### Answers

- `modelly.experiments`: a study as one object. `ScenarioSpace` (ranges, log and integer
  ranges, choices, fixed values, checked against the model's `Scenario`), designs (full
  factorial, Latin hypercube, Sobol, Halton, custom), replicates with one seed per run, a
  Parquet results store with a DuckDB view that resumes after a crash, and executors:
  serial, threads, processes, Dask, Ray, SLURM and PBS job arrays (pluggable through the
  `modelly.executors` entry points). The same experiment gives the same results on every
  executor. `modelly experiment run|status spec.toml`.
- `modelly.calibrate`: `ABCRejection`, `ABCSMC` (adaptive tolerances, resumable),
  `SimulatedMoments` and a basic `BayesOpt`; priors, targets and distances; a `Posterior`
  with summaries, HDIs, posterior predictive runs and plots. Verified by recovering the
  parameters of SIR and predator-prey models from synthetic data. `modelly calibrate`.
- `modelly.sensitivity`: one-at-a-time, Morris, Sobol (Saltelli sampling, bootstrap intervals;
  matches the Ishigami indices) and PAWN, on a model, a function or a Gaussian-process
  emulator. `modelly sensitivity`.
- `DataCollector.to_parquet`, `to_arrow` and `query` (DuckDB).

### Trust

- Provenance: `modelly run` writes the outputs and a manifest (code hash, versions, compiled
  or pure build, platform, scenario, seeds, input and output hashes); `modelly verify` reruns
  it and names the first differing output; `modelly bundle` packs a byte-identical zip for
  Zenodo; `modelly odd` writes an ODD protocol skeleton from the code.
- `modelly.timetravel`: `Recorder` keeps checkpoints within a memory or disk budget;
  `at(step)` rewinds, a replay is bit-identical with a straight run, `branch` forks futures,
  and `diff` finds the first step, agent and attribute where two runs part.
- A determinism suite: every example, compiled and pure-Python, straight and resumed from a
  checkpoint, against stored digests that every platform must reproduce
  (`python -m modelly.dev golden`). Property-based tests for columns, cohorts, cell spaces,
  checkpoints and designs.

### Reach

- `modelly.space.geo` (extra `geo`): `GeoSpace` with a coordinate reference system, regions,
  contiguity and distance queries in metres, GeoParquet and GeoJSON export; `RasterLayer`
  (GeoTIFF); `RoadNetwork` with routing and travel times; synthetic populations by
  iterative proportional fitting.
- `modelly.space.networks`: temporal networks (O(changed edges) updates), multilayer networks,
  contact matrices, network collectors; NetworkX, igraph and CSV import.
- `modelly.llm`: language-model agents with a provider-agnostic client (Anthropic,
  OpenAI-compatible and local endpoints, a fake provider), a deterministic SQLite response
  cache with offline replay, token and cost budgets, retries, structured decisions with
  schema validation, and `LLMAgent`. API keys never reach caches, checkpoints or logs.
- `modelly.zoo`: twelve validated reference models (age-structured SEIR, Nagel-Schreckenberg
  traffic, Bass diffusion, Deffuant and Hegselmann-Krause opinions, Axelrod culture, kinetic
  and Bouchaud-Mezard wealth, a double-auction order book, forest fire, an energy-budget
  population, vector-borne transmission), each with a validation test against an analytic or
  known result. `modelly zoo list|info|copy`, `modelly new --from-zoo`.
- New examples: a commuting city and a three-layer epidemic (spatial), persona agents
  deciding through `modelly.llm`.

### Experience

- Modelly Studio: `modelly studio model.py:Model` opens a browser app with a parameter panel
  built from the scenario, run controls, space and time-series views, an agent table, a
  timeline scrubber on time travel with replay from any step, profiler and lint panels, and
  exports (figures, data, checkpoints, GIF).
- `modelly new` with grid, network, continuous and cohort templates (seeded, tested, linted).
- `modelly lint --fix` and `--diff` for MDL001, MDL002, MDL003 and MDL009; new rules MDL010
  (a lambda or closure sent to spawned workers, which fails on Windows and macOS) and MDL012
  (a network or LLM call that bypasses `modelly.llm`).
- `python -m modelly.dev gate`: the local gate in Python, for contributors without bash.
- Jupyter: `%load_ext modelly.ipython` for `%modelly lint` and `%modelly profile`, and a rich
  display of a `Model`.
- Publication figures (`modelly.viz.styles.paper()`, journal widths, colour-blind-safe
  palettes) and GIF or MP4 export of any space view (extra `video`).
- Plugins: entry-point groups for spaces, executors, samplers, collectors, Studio views and
  lint rules (`modelly.plugins`).
- `modelly` lists its fourteen commands by task: start, run and explore, publish.
- Docs: six domain tutorials, an eight-session course pack, a gallery, guides for every new
  module, and the roadmap for 1.3 to 2.0.

### Performance and platforms

- `fastset.c`: `AgentSet` type filtering, `select`, attribute reads in `agg` and weak-set
  listing in C (0.45 to 0.95 of the Python time on 20,000 agents), with Python twins.
- The four compiled modules run on free-threaded CPython with the GIL off; free-threaded
  wheels are built, as are Windows ARM64 wheels on a native runner.
- `modelly bench`: the playbooks in alternating rounds, CPU pinning where the OS allows it, a
  JSON-lines history and a regression check (exit 1).
- Memory baseline per agent recorded in `docs/performance.md`.
- Every text file is opened as UTF-8 (ruff `PLW1514`), checkpoints are written atomically, and
  hashed text outputs use LF line endings, so results and hashes match on every OS.

### Changed

- Reading or writing a `Column` on a removed agent raises `ColumnMissingError` (an
  `AttributeError`) instead of reading a stale row. Errors for a full cell, a missing agent
  and a removed agent name the agent and the model time.
- Deprecations raise `ModellyDeprecationWarning`, both a `DeprecationWarning` and a
  `FutureWarning`, naming the replacement and the removal in 2.0.
- A checkpoint loads only into the Modelly minor version that wrote it: 1.2 checkpoints do not
  load in 1.3.
- Every public name has a stability level (`docs/api_stability.toml`): what 1.2 had is stable,
  what 1.3 adds is provisional.

### Fixed

- The Epstein example's scenario declared `rng: int = 42`, overriding any seed; the virus
  network example built a different network in each process. Both are seeded from the model.
- The Epstein, prisoner's dilemma and Sugarscape examples can be checkpointed.
- Browser tests bind free ports, so two test runs can share a machine.

## 1.2.0 - 2026-10-24

### Added

- Checkpoints: `model.save(path)`, `Model.load(path)` and `model.checkpoint_every(n, pattern)`.
  A run resumed from a checkpoint, in a new process, gives exactly the run it would have been:
  both random generators, the event scheduler, spaces, columns and collected data are saved.
  A checkpoint made with the compiled random core loads into the pure-Python one and the other
  way round. Loading runs pickle: only load files you trust. Lambdas and closures are refused
  with an error naming them.
- Versioned documentation: `/Modelly/` is the latest release, `/Modelly/dev/` is main and
  each minor release keeps its own folder (`/1.0/`, `/1.1/`, `/1.2/`), with a version switcher
  in the navbar and a banner on older versions.
- `modelly profile --sizes 1000,4000` (and `modelly.profile.compare_sizes`) profiles a model
  at several population sizes and compares the cost per agent, so the MDL101 hint also works
  for models whose population does not change during a run.
- `MetaAgents.cache_build(score)`: scores each candidate group once across repeated
  `find_combinations` calls, with `invalidate()` and an optional `maxsize`.
- Windows wheels (x86-64) with the compiled modules.

### Changed

- `modelly lint --help`, `modelly migrate --help` and `modelly profile --help` name the
  command as it was run (`modelly <cmd>`, or `python -m modelly.<cmd>`).
- MDL107 follows imports of agent classes from other files in the linted tree, so models split
  into several modules are checked.
- A `CellCollection` built without a generator takes its cells' or agents' model generator, so
  the same seed gives the same draws.
- The creation path of meta agents returns `MetaAgent` instead of `Any`.

### Performance

- Removing an agent that belongs to meta agents reads its own memberships instead of copying
  the whole membership table: 2,000 removals among 10,000 agents went from 100 s to 0.16 s.
- `fastcell.c` uses only the public C API, with the same speed as 1.1.0.
- The Sugarscape playbook ranks cells only when a forager's best cell is taken: 2.5x faster
  than in 1.1.0, 32x faster than Mesa 2.3 (was 12x), same results.

### Fixed

- A continuous space restored from a pickle kept a copy of the agent positions, so later moves
  were lost; it now keeps a view.
- The empty-cell index keeps its order through pickling, so a restored grid draws the same
  empty cells.
- `DataCollector` reporters are picklable.

## 1.1.0 - 2026-10-24

### Added

- `modelly.profile`: a runtime profiler. `with Profiler(model) as prof: model.run_for(n)`, then
  `prof.report()` or `prof.to_dataframe()`, gives the time of each step by agent class and
  method (calls, agents per call, microseconds per agent), data collection and scheduled events,
  with hints that point at the matching lint rule. `python -m modelly.profile model.py:MyModel`
  runs it from the command line. Results are identical with and without the profiler, and the
  instrumented methods are restored exactly on exit.
- `python -m modelly` and a `modelly` script: one entry point for `lint`, `migrate` and `profile`,
  with `--version` and a help page listing every command.
- `AgentPortrayalStyle.filled` (Altair backend); extra keywords to `draw_agents` reach
  `mark_point` instead of being dropped.
- Three benchmark playbooks, each for Mesa 2.3 and Modelly with agreement and determinism
  checks: `schelling` (27x), `boltzmann_wealth` (7.4x) and `sugarscape` (12x).

### Linter

- New rules: MDL005 wall-clock or OS entropy in model code, MDL006 ordering by `id()` or
  `hash()`, MDL007 removing agents while looping over the population, MDL008 `global` state in
  a model method, MDL009 editing `model.agents` directly, MDL106 DataFrames built inside `step`,
  MDL107 a per-agent loop that only writes columns.
- MDL001 also catches unseeded `Random()`, `SystemRandom` and numpy generators without a seed,
  and resolves imports (`default_rng(seed=7)` is no longer flagged); MDL004 skips `__slots__`
  and `ClassVar`.
- `# noqa: MDLxxx` suppression, `[tool.modelly.lint]` in `pyproject.toml` (`select`, `ignore`,
  `per-file-ignores`), `--explain CODE` with a bad and a fixed example, `--statistics`,
  `--format github` and `--quiet`.
- Detailed `--help` for `lint` and `migrate`, with examples and exit codes; `docs/lint.md`
  lists every rule.

### Performance

- Moving an agent between cells runs in a third compiled module (`modelly/_native/fastcell.c`):
  one move is 205 ns to 107 ns, the cell-list playbooks 7 to 14% faster, with the same results.
  Subclasses that override `add_agent` or `remove_agent` keep their overrides; the pure-Python
  twin is used when the module is not built.
- `import modelly` no longer walks the stack to name its loggers (about 30 ms less).

### Fixed

- Matplotlib marker groups are drawn in first-seen order instead of set order, so the
  layering no longer changes from run to run.
- `run_batch` no longer emits Python's multi-threaded fork `DeprecationWarning` for closure
  batches.

### CI

- Release wheels are built on tags and manual runs only; superseded runs are cancelled;
  docs-only changes skip the build; Dependabot groups its updates monthly; the `examples` job,
  which checked out a missing repository, is gone (the test matrix already runs `tests/examples`).

## 1.0.1 - 2026-10-24

The 1.0.0 code, published to PyPI under a new number: PyPI does not accept a second upload of
1.0.0, and its `modelly-abm 1.0.0` predates the domain package layout.

## 1.0.0 - 2026-10-24

First release.

### Package layout

Every module lives in a domain package; the top-level names (`modelly.Agent`, `modelly.Model`,
`modelly.DataCollector`, `modelly.Column`, `modelly.CohortTable`, `modelly.FastRandom`,
`modelly.run_batch`, `modelly.run_grid`) are the short way in.

| Package | Contents |
|---|---|
| `modelly.core` | `agent`, `model`, `agentset`, `columns`, `rng`, `exceptions` |
| `modelly.space` | discrete spaces; `modelly.space.continuous` |
| `modelly.time` | `schedule`, `signals` |
| `modelly.data` | `collector`, `reporters`, `recorders` |
| `modelly.behaviour` | `actions`, `states`, `meta_agents` |
| `modelly.scenarios` | scenarios |
| `modelly.batch` | `runs`, `cohorts` |
| `modelly.viz` | `solara`, `console`, `render`, `altair`, `mpl` |

### Core

- `Model`: owns the scenario, both seeded random generators, simulation time and the event
  scheduler (`step`, `run_for`, `run_until`, `schedule_event`, `schedule_recurring`).
- `Agent` and `AgentSet`: ordered sets with `select`, `select_random`, `shuffle_do`, `do`,
  `map`, `get`, `set`, `agg`, `groupby`; the model's registries are `dict`-backed (membership
  in C), views never hold strong references, and birth and death skip every listener check
  when nobody observes the model.
- `Column`: agent attributes stored in model-owned numpy arrays, one table per agent class,
  with whole-population views (`model.columns[Cls].<name>`), `draw`, `do_where`,
  `remove_where`, `where`, `thin` and `to_dataframe`; per agent, a column is a fast property
  reading the row through a `memoryview` (27 ns per read). `Agent.column_specs()` lists them.
- `Scenario`: typed parameters plus the seed, with `spawn_replications` for reproducible sweeps.

### Random numbers

- `FastRandom` (`model.random`): exactly the standard library's numbers for a seed, faster.
  A compiled core (`modelly/_native/fastrng.c`) runs `randint`, `choice`, `shuffle`, `sample`
  and `_randbelow` in C on CPython's own Mersenne Twister state (`randint` 59 ns against 193 ns,
  `shuffle` 38 ns against 206 ns per element), verified against `random.Random` at import; the
  pure-Python `PyFastRandom` is the fallback.
- `do` and `shuffle_do` on the model's agent registries, and the breadth-first walk behind
  `Cell.get_neighborhood`, run in a second compiled module (`modelly/_native/fastloop.c`),
  with an identical pure-Python twin used when it is not built (`MODELLY_PURE_PYTHON=1`).

### Space and time

- Discrete spaces: orthogonal Moore and Von Neumann grids, hexagonal grids, networks and Voronoi
  meshes, with per-cell neighbourhood caches, property layers backed by numpy arrays and an
  O(1) empty-cell index.
- `CellIndex`: integer rows and a sparse adjacency for any discrete space (`counts`,
  `neighbor_sum`, `random_neighbor`), `Occupancy` and `claim` for cell membership as a column,
  and `track` to list and draw agents placed by a row column.
- Continuous space with positions in one numpy array, one KD-tree per step for neighbour
  queries (`neighbors_within`, `pairs_within`) and `move_all`.
- Event scheduler on a heap with lazy cancellation and compaction.

### Populations and experiments

- `CohortTable`: counted populations (one row per state, no agent objects) with binomial
  `thin`, `split` and `draw`, `merge` and `compact`, with the law of the individual model.
- `run_batch` and `run_grid`: experiments over processes with results in the sequential
  order and one `SeedSequence` seed per run.

### Data and tooling

- `DataCollector` with model, agent, agent-type and table reporters; agent rows gathered
  column-wise and sliced straight from column tables when possible.
- Browser visualization (Solara), matplotlib and altair backends.
- `python -m modelly.migrate`: a codemod and guide for models written for Mesa.
- `python -m modelly.lint`: static checks for models (random draws outside the model's
  generators, missing `super().__init__`, population scans and more).
- Benchmarks: the bundled reference models, five playbooks written for Mesa 2.3 and for
  Modelly with an agreement and determinism check, and the evaluation method in
  `docs/performance.md`. On a research model ported line for line from Mesa 2.3, Modelly is
  12% faster with bit-identical output; written with columns and cohorts, the playbooks run
  4.3 to 213 times faster.
- Platform wheels for Linux and macOS with the compiled core, a pure wheel and the sdist for
  every other platform.

### Internals

- Every module is at most 300 lines and every function body at most 25 lines, except the
  per-agent render loop of the Altair backend, kept inline on purpose.
- Tests mirror the package layout; `tests/native` runs the compiled loops against their twins.
