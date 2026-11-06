# What's new

What each release lets you do, in a few lines per feature, newest first. Every feature links to
its guide. The [changelog](https://github.com/RemiPelloux/Modelly/blob/main/CHANGELOG.md) has
the full detail of every change, and [Deprecations](deprecations.md) what is going away and
when.

Each release adds its section here before it is tagged: the release script refuses a release
whose notes are missing (see "Release notes" in
[CONTRIBUTING](https://github.com/RemiPelloux/Modelly/blob/main/CONTRIBUTING.md)).

## Unreleased

### New

- **Docs for AI assistants**: every page of this documentation is also plain Markdown. The
  *Copy page* button under each title puts it on your clipboard for a chat; replace `.html`
  with `.md` in any address to read it; [llms.txt](https://remipelloux.github.io/Modelly/llms.txt) lists every page and
  [llms-full.txt](https://remipelloux.github.io/Modelly/llms-full.txt) holds them all in one file.
- **A home page that finds the guide**: type a task (calibrate, GPU, from R) and the matching
  guides are listed; the benchmark against Mesa 3.5 is drawn model by model. [Home](index.md)

### Fixed

- **Causes and explanations** gives the variance reduction of common random numbers as its
  spread over ten seeds (24 to 62 times on the Bass example, median 42) instead of one seed's
  value. [Causes and explanations](explain.md)

## 1.5.0 - 2026-11-03

**Ecosystem and collaboration.** Publish a model on the hub with its card, decide and explain
with intervals, give agents memories and inner dynamics, and work from R, Julia, a classroom or
another language. The last release before 2.0: everything 2.0 changes now warns or changes no
call, and `modelly migrate --check-2.0` lists what a project must change.

### New

- **Decisions**: compare strategies on the same chance events, so their differences come with
  tight intervals; see which are cost-effective and at what price; check which hold up across
  many possible futures; and search a policy's parameters. A worked study asks which age group
  should get 10,000 vaccine doses. [Decisions](decide.md)
- **Accessible, and in five languages**: Studio and the docs pass the automated WCAG 2.2 AA
  checks; Studio can be zoomed, works with screen readers and the keyboard, and speaks
  French, Spanish, Portuguese and Chinese (`--language fr`), right to left where the language
  is. The getting-started page is translated too. [Accessibility and languages](accessibility.md)
- **For classes**: a twelve-session course with instructor notes and assessments, a track for
  instructors coming from NetLogo, and a classroom mode in Studio where the instructor shares
  parameters and every student's run lands in one table. [Course](course/index.md)
- **Studio for everyone**: open a hub model by name with no code tabs
  (`modelly studio --hub age_seir --no-code`), compare scenarios with intervals, read the
  model card, build a teaching model from a form and download its code, and export a report
  (HTML or PDF) with the figures, the card and how to rerun the run.
  [Studio](studio.md#studio-for-everyone)
- **Language-model agents that remember, plan and talk**: agents keep a memory that is
  summarised as it grows, write plans, reflect, call functions of the model before answering,
  and hold conversations with each other, many at once. A 500-trader market runs offline and
  replays from its cache, and an evaluation harness compares providers on behaviour,
  consistency and cost. [Language-model agents](llm_agents.md#memory)
- **Modelly from Julia**: `Modelly.jl` runs and calibrates models from Julia, returns
  DataFrames and hands over agent columns without copying them.
  [From R and Julia](r_and_julia.md#the-julia-package)
- **Modelly from R**: the `modelly` R package runs and calibrates models from R and returns
  data frames, with no Python to write: `modelly_calibrate(...)` fits the SIR tutorial and
  prints its posterior. [From R and Julia](r_and_julia.md#the-r-package)
- **Causes and explanations**: the effect of an intervention with an interval, and how much
  running both arms on the same chance events tightened it; the agents an outcome depended on
  (it finds an outbreak's index case); what a recorded run would have done with one change;
  and how much each parameter moved an emulator's prediction. [Causes and explanations](explain.md)
- **The model hub**: `modelly hub search malaria` finds published models, `modelly hub info`
  shows what each is for and how to cite it, and `modelly hub install` gets one, checking its
  hash and signature first. `modelly hub publish` prepares your model's entry, with a DOI from
  Zenodo and a Sigstore signature when you ask. All eighteen zoo models are on it.
  [The model hub](hub.md)
- **Inputs that change inside a step**: `Forcing(function)` and `Series(times, values)` drive
  an `AgentODE` or `solve_batch` at the times each system's own steps land on (daylight, a
  dosing schedule, a measured series), instead of holding the value over the model's step.
  [ODEs in every agent](agent_odes.md#inputs-that-change-inside-the-step)
- **The state inside a step**: with `dense_output=True`, `ode.at(t)` reads every agent's state
  at any time of the last step on the solver's interpolant, so an agent acting at 14:00 sees
  the value at 14:00. [ODEs in every agent](agent_odes.md#reading-the-state-inside-the-step)
- **Delays, noise and the mean-field limit**: an agent's equation can read its own state some
  time ago (`Delay`), carry noise drawn from the model's seed (`AgentSDE`, Euler-Maruyama or
  Milstein), and run next to its ODE limit to show how far the agents stray from it
  (`Companion`). [ODEs in every agent](agent_odes.md#delay-equations)
- **ODE parameters by gradient**: `ode_phase` puts an ODE into a differentiable model, so a
  clearance or growth rate is fitted to data by gradient descent.
  [Differentiable models](differentiable.md#odes-in-a-differentiable-model)
- **A zoo model with an ODE in every host**: `within_host`, an outbreak whose hosts each carry
  a viral-load ODE and become infectious the instant their load crosses a threshold. A hundred
  thousand hosts run sixty days in about fourteen seconds.
  [Within-host epidemic](zoo/within_host.md)
- **Model cards**: a short `card.toml` beside a model says what it is for, what it must not be
  used for, its data, how it was validated, its limits and who decisions taken with it could
  affect. `modelly card stamp` runs the validation tests and records the source they passed
  on, and `modelly card check` fails once the model has changed since. All eighteen zoo models
  have one, at the end of their page. [Model cards](model_cards.md)
- **Plugin API v1**: the way packages extend Modelly is now stable and frozen for 1.x. A
  plugin says which Modelly it supports with its usual `modelly-abm>=1.5,<2` dependency, and a
  plugin built for another version is skipped instead of breaking the run.
  `modelly new --template plugin` starts one, and `modelly plugins --check` shows what is
  installed. [Plugins](plugins.md)

### Deprecated

- **Typed scenarios**: in 2.0 a `Scenario` subclass is typed and validated. An attribute
  without an annotation, a parameter the scenario does not declare, or a value of another type
  than its annotation now warns and says what to write. `modelly migrate --check-2.0 src/`
  lists everything a project must change before 2.0. [Deprecations](deprecations.md)

### Fixed

- **Pages made by `modelly export-web`** keep small parameters as they are: a tolerance of
  one in a billion used to be rounded to zero by its slider.

## 1.4.3 - 2026-11-02

**An ODE in every agent.** Continuous dynamics inside each agent (the virus in a host, the
energy budget of an animal, the potential of a neuron), integrated for the whole population at
once.

### New

- **`solve_batch`**: `solve_ivp` for many independent systems. Each system takes exactly the
  steps its own `solve_ivp` call would take and ends at the same values, while the right-hand
  side is evaluated once per stage for all of them: 100 to 300 times faster than a loop of
  `solve_ivp` calls from a thousand systems up. A system's result is the same, bit for bit,
  alone or among a hundred thousand others. [ODEs in every agent](agent_odes.md)
- **`ODEEvent`**: the moment a quantity crosses a threshold, located per system on the step's
  interpolant, as `solve_ivp`'s `events=` does; terminal (stop there) or recorded, upward,
  downward or both.
- **`AgentODE`**: an ODE per agent inside a model. The state lives in the agents' columns,
  events call back into the model (a host becomes infectious the instant its virus passes a
  level), and terminal events resume within the step (a neuron fires and resets). Stiff systems
  run through `solve_ivp`'s implicit methods with a block-diagonal Jacobian pattern.

The new names are provisional (`docs/api_stability.toml`). Nothing else changed: every
playbook gives 1.4.2's results.

## 1.4.2 - 2026-10-29

A fix for numpy datasets.

### Fixed

- **Two models of the same agent class** with a numpy dataset
  (`DataRegistry.track_agents_numpy`) no longer read each other's values, a model restored by
  `Model.load` reads its own, and a checkpoint loads in a fresh process. Checkpoints written by
  1.4.0 and 1.4.1 load as before.
- The SQL recorder stores `agent_id` as an integer, as the other recorders do.

## 1.4.1 - 2026-10-29

Three operations that grew quadratically with the size of a run now grow linearly. Results are
unchanged.

### Faster

- **Parquet recording** of long runs: 2,000 agents for 200 steps in 1.0 s instead of 7.9 s, and
  twice the steps take twice the time.
- **Removing cells** from a discrete space or a network: half of a 32,000-node network in
  0.14 s instead of 7.9 s.
- **Batches of many short runs** (`run_batch`, `run_grid`): workers take tasks in chunks, so
  20,000 short tasks spend 0.01 s in hand-offs instead of 0.49 s.

### Fixed

- The JSON recorder returns one row per agent for a numpy dataset, as the others do.
- A network cell replaced at the same coordinate can no longer be returned by
  `find_nearest_cell`.

### Documentation

- The site's header has six sections, each with its own sidebar, instead of a menu that ran
  off the screen.

## 1.4.0 - 2026-10-29

**Scale out and connect.** One model split across processes, on a GPU, differentiated,
corrected by live data, coupled to fields and ODEs, started from a synthetic population, and
shared as a web page. No playbook is slower than 1.3.3 and every output is identical.

### New

- **Split runs** (`modelly.distributed`): one model divided between processes or machines
  (local, MPI, Dask or Ray), with ghost agents at the borders and agents migrating with their
  own random streams. The result equals the single-process run, byte for byte, which the tests
  check at 1 to 16 partitions. [From laptop to cluster](distributed.md)
- **Per-agent random streams**: with `agent_streams = True`, each agent draws its own numbers,
  whatever the activation order or the population. [Determinism](determinism.md)
- **GPU backend** (`modelly.gpu`): column phases, cohorts and cell operators on CuPy or JAX,
  with a random stream that draws the same numbers on every backend. The grid epidemic at ten
  million agents runs 34 times faster than on one CPU core, bit for bit. [GPU](gpu.md)
- **Differentiable models** (`modelly.diff`): gradients of a model's outputs with respect to
  its parameters through JAX, checked against finite differences, and gradient-based
  calibration. [Differentiable models](differentiable.md)
- **Live data and assimilation** (`modelly.stream`): sources reading files, HTTP, MQTT or Kafka;
  ensembles; particle filters and ensemble Kalman filters that correct a running model as data
  arrives, and forecast from it. [Live data and assimilation](assimilation.md)
- **Coupling** (`modelly.couple`): grid fields that diffuse, drift and decay, ODEs and
  stock-flow models, run with the agents on their own clocks, with a schedule checked before
  the first step. [Coupling fields and ODEs](coupling.md)
- **Emulators, active learning and history matching** (`modelly.emulate`): fast statistical
  stand-ins for a slow model, designs chosen where the emulator is least sure, and the
  plausible parameter space narrowed in waves. [Emulators](emulators.md)
- **Synthetic populations** (`modelly.population`): people and households drawn from census
  tables, assigned to homes, schools and workplaces, with their contact network.
  [Synthetic populations](population.md)
- **Modelly in the browser**: `modelly export-web` writes a static site that runs the model in
  any browser, no installation. [In the browser](browser.md)
- **Studio II**: ensemble bands, assimilation, an experiment browser, calibration and
  sensitivity results, a WebGL map for 100,000 agents, and export of a session as a script or
  a verifiable bundle. [Studio](studio.md)
- **More tools**: a NetLogo translator ([From NetLogo](netlogo.md)), `modelly lint` as a
  language server and a pre-commit hook ([Checking a model](lint.md)), xarray export, results
  read from R and Julia ([From R and Julia](r_and_julia.md)), memory-mapped columns for
  populations larger than memory, `modelly bench --against` a release, and five new zoo models
  on real maps and coupled processes ([Model zoo](zoo/index.md)).

### Changed

- The event heap is compiled: event-heavy models run faster with the same ordering.
- Data collection reads column attributes in C: 0.47 of 1.3.3's time.

### Deprecated

- `modelly.space.geo.ipf` and `synthesize_population`: import them from `modelly.population`;
  they go in 2.0.

## 1.3.3 - 2026-10-27

The codemod (`python -m modelly.migrate`) handles Mesa 3.5's own examples: eight of its ten
bundled examples migrate and run. The library is 1.3.2's. [Migrating from Mesa](migrating_from_mesa.md)

### Fixed

- `mesa.experimental.scenarios` and `mesa.experimental.data_collection` map to their Modelly
  modules, and a Mesa module with no Modelly equivalent is reported instead of rewritten.

## 1.3.2 - 2026-10-25

A correctness release for calibration.

### Fixed

- **ABC-SMC near a bounded prior**: particles close to a bound were over-weighted (by 17% next
  to it). The weights are now exact; posteriors from the same seed differ from 1.3.1's.
  [Calibration](calibration.md)

### New

- **A performance guard for contributors**: `python -m modelly.dev perf` times 17 core
  operations against the last release and fails when one is slower; a git hook runs it before
  each commit.

## 1.3.1 - 2026-10-24

Reading a column, walking a neighbourhood and moving between cells cost what they did in 1.2.0
again (1.3.0 had made them slightly slower). Free-threaded builds keep their safe paths.

## 1.3.0 - 2026-10-24

**Answers and trust.** Calibrate, explain and publish a model, on Windows, macOS and Linux.

### New

- **Experiments** (`modelly.experiments`): a study as one object (parameter space, design,
  replicates, a results store that resumes after a crash) that gives the same results on
  threads, processes, Dask, Ray, SLURM or PBS. [Experiments and sweeps](experiments.md)
- **Calibration** (`modelly.calibrate`): ABC rejection, ABC-SMC, simulated moments and Bayesian
  optimisation, with posteriors, intervals and predictive runs. [Calibration](calibration.md)
- **Sensitivity analysis** (`modelly.sensitivity`): one-at-a-time, Morris, Sobol and PAWN.
  [Sensitivity analysis](sensitivity.md)
- **Provenance**: `modelly run` writes a manifest of everything needed to repeat a run,
  `modelly verify` repeats it and names the first output that differs, `modelly bundle` packs
  an archive for Zenodo, `modelly odd` drafts the ODD protocol. [Reproducible studies](provenance.md)
- **Time travel** (`modelly.timetravel`): rewind to any step, replay exactly, branch futures
  and find where two runs part. [Time travel](timetravel.md)
- **Geospatial models, networks and language-model agents**: spaces with real coordinates,
  rasters and road networks ([Geospatial models](geospatial.md)); temporal and multilayer
  networks ([Networks](networks.md)); agents that decide through a language model, cached and
  reproducible ([Language-model agents](llm_agents.md)).
- **The model zoo**: twelve reference models, each validated against a known result.
  [Model zoo](zoo/index.md)
- **Studio**: a browser app with a parameter panel, run controls, views, a timeline and
  exports. [Studio](studio.md)
- **Getting started faster**: `modelly new` templates, `modelly lint --fix`, Jupyter magics,
  publication figures, and plugins. [Starting a project](new_project.md)
- **A determinism suite**: every example compiled and in pure Python, straight and resumed,
  against stored digests that every platform must reproduce. [Determinism](determinism.md)

### Changed

- Reading a column of a removed agent raises `ColumnMissingError` instead of reading a stale
  row.
- Deprecations raise `ModellyDeprecationWarning`, naming the replacement.
- A checkpoint loads only in the minor version that wrote it.
- Every public name has a stability level: stable or provisional.

## 1.2.0 - 2026-10-24

### New

- **Checkpoints**: `model.save`, `Model.load` and `checkpoint_every`. A resumed run, even in a
  new process, is the run it would have been. [Checkpoints](checkpoints.md)
- **Versioned documentation**, with a version switcher.
- `modelly profile --sizes` compares the cost per agent at several population sizes.
  [Profiling a model](profile.md)
- Windows wheels with the compiled modules.

### Faster

- Removing agents that belong to meta agents: 2,000 removals among 10,000 agents in 0.16 s
  instead of 100 s.

### Fixed

- A continuous space restored from a checkpoint keeps moving its agents; a restored grid draws
  the same empty cells.

## 1.1.0 - 2026-10-24

### New

- **The profiler** (`modelly.profile`): the time of each step by agent class and method, with
  hints that point at the matching lint rule. [Profiling a model](profile.md)
- **One `modelly` command** for `lint`, `migrate` and `profile`.
- **Seven new lint rules** (wall-clock time in a model, ordering by `id()`, removing agents
  while looping, and more), `# noqa` suppression and settings in `pyproject.toml`.
  [Checking a model](lint.md)

### Faster

- Moving an agent between cells runs in C: 205 ns to 107 ns per move.

## 1.0.1 - 2026-10-24

The 1.0.0 code under a new number, since PyPI does not accept a second upload of 1.0.0.

## 1.0.0 - 2026-10-24

**First release.** A Python agent-based modelling framework whose programming model is
compatible with Mesa's, written from scratch for speed and reproducibility.

### New

- **Agents, models and agent sets**, seeded random generators whose numbers are the standard
  library's for a seed, and an event scheduler. [Getting started](getting_started.md)
- **Columns**: agent attributes in model-owned numpy arrays, so a phase can update the whole
  population at once while each agent remains an object. [Performance](performance.md)
- **Cohorts**: counted populations, one row per state instead of one object per individual,
  with the law of the individual model. [Vectorised phases](vectorised_phases.md)
- **Spaces**: grids, hexagonal grids, networks, Voronoi meshes and continuous space.
- **Compiled cores** for random draws and agent loops, each with a pure-Python twin that gives
  the same results.
- **Data collection, visualisation, batch runs**, a codemod for models written for Mesa
  ([Migrating from Mesa](migrating_from_mesa.md)), and a linter for models
  ([Checking a model](lint.md)).
