# Studio

Modelly Studio, the browser app behind `modelly studio`. How to use it is in [Modelly Studio](https://remipelloux.github.io/Modelly/dev/studio.html).

Module

Contents

modelly.studio.config

StudioConfig

modelly.studio.params

Parameter, parameters_of

modelly.studio.loader

load_model_class, load_portrayal

modelly.studio.session

StudioSession

modelly.studio.timeline

GuardedRecorder, ReplayTimeline, track

modelly.studio.data

series, agent table, figures and export files

modelly.studio.recording

SessionRecording, Segment, literal

modelly.studio.exports

session_script, bundle_bytes, bundle_spec, script_name

modelly.studio.ensembles

ensemble_of, band_series, session_bands, reporter_operator

modelly.studio.assimilation

assimilate, FilterSettings, Assimilation, posterior_weights

modelly.studio.browser

ExperimentBrowser

modelly.studio.analyses

load_analyses, view_of, AnalysisView

modelly.studio.figures

band_figure, ess_figure, weights_figure, trajectory_figure, against_figure, series_figure

modelly.studio.scene

Scene, scene_of, encode, element_count

modelly.studio.assets

required_assets, missing_assets, fetch_assets

modelly.studio.mapview

MapWidget, MapView

modelly.studio.app

StudioApp, Page, new_session

What one Studio server shows: the model, its portrayal and the panels’ settings.

The command line builds a `StudioConfig` and hands it to the Solara app through one environment variable as JSON, so the app module finds it however Solara imports it.

#### `class StudioConfig(target: str, portrayal: str | None = None, seed: int = 42, every: int = 1, profile_steps: int = 50, table_rows: int = 100, memory_budget_mib: int = 256, results: str | None = None, observations: str | None = None, analysis: str | None = None, mode: str = 'full', language: str = 'en', classroom: str | None = None)`

The settings of a Studio session.

**Variables:**

- **target** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – `path/to/model.py:ModelClass` or `package.module:ModelClass`.
- **portrayal** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – `path/to/app.py:function` or `package.module:function` returning an `AgentPortrayalStyle` per agent; one colour per agent class when None.
- **seed** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – The seed the first run starts from.
- **every** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Steps between two checkpoints of the timeline.
- **profile_steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – How many of the last steps the profiler panel sums.
- **table_rows** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Rows the agent table shows.
- **memory_budget_mib** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Mebibytes the timeline’s checkpoints may take.
- **results** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – An experiment’s results store folder, for the Experiments tab.
- **observations** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – A CSV file of observations (a `time` column, one column per reporter), for the Assimilation tab.
- **analysis** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – `path/to/file.py:function` returning posteriors or sensitivity results, for the Analysis tab.
- **mode** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"full"`, or `"no-code"` for the tabs of people who do not write code.
- **language** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the language of the labels (`modelly.studio.i18n`), English by default.
- **classroom** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – a folder shared by a class (`modelly.studio.classroom`), or None.

#### `property memory_budget: int`

The checkpoint budget in bytes.

#### `property source_file: Path | None`

The model’s `.py` file when the target names one, for the lint panel.

#### `to_json() → str`

The config as JSON.

#### `classmethod from_json(text: str) → StudioConfig`

A config from `to_json` output.

#### `export() → None`

Put the config in the environment, for the app module to read.

#### `classmethod from_environment() → StudioConfig`

The config `export` put in the environment.

**Raises:**

[**RuntimeError**](https://docs.python.org/3/builtins/exceptions.html#RuntimeError) – When there is none, i.e. the app was not started by `modelly studio`.

The parameter panel’s fields, read from a model’s `Scenario` and constructor.

Every field of the Scenario class the model’s `scenario` argument defaults to, and every keyword its constructor takes with a default, becomes a `Parameter`. Its kind picks the widget: `bool` a checkbox, a `Literal` or an `Enum` a select, a float between 0 and 1 a slider, another number a number field, a string a text field. Anything else (a tuple, a dict, None) is shown but cannot be changed from the panel.

#### `class Parameter(name: str, kind: str, default: Any, choices: tuple = ())`

One field of the parameter panel.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The scenario field or constructor keyword.
- **kind** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The widget: one of `bool`, `int`, `float`, `fraction` (a 0 to 1 slider), `choice`, `text` or `fixed` (shown, not editable).
- **default** (*Any*) – The value the model is built with unless it is changed.
- **choices** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)) – The values a `choice` offers.

#### `property editable: bool`

Whether the panel lets the value be changed.

#### `kind_of(value: Any, annotation: Any = None) → tuple[str, tuple]`

The widget kind for `value` and, for a `choice`, the values it offers.

#### `parameters_of(model_class: type[Model]) → list[Parameter]`

The panel’s fields for `model_class`: its constructor’s, then its Scenario’s.

Find the model class and the portrayal a `modelly studio` command line names.

A `path/to/model.py` is imported under its package’s dotted name when its folders are packages (`modelly/examples/basic/schelling/model.py` is `modelly.examples.basic.schelling.model`), else under its own name with its folder on `sys.path`. Either way the classes are importable by name, so checkpoints of the model load again, and a model’s `from agents import Sheep` finds the file next to it.

#### `import_source(source: str) → ModuleType`

Import `source`: a `.py` file or a dotted module name.

**Raises:**

**TargetError** – When the file does not exist or the module cannot be imported.

#### `load_model_class(target: str) → type[Model]`

The Model subclass `path/to/model.py:Class` or `package.module:Class` names.

**Raises:**

**TargetError** – When it cannot be found or is not a Model subclass.

#### `load_portrayal(target: str) → Callable`

The agent portrayal function `path/to/app.py:function` names.

**Raises:**

**TargetError** – When it cannot be found or is not callable.

#### `module_name(path: Path) → tuple[Path, str]`

The folder to put on `sys.path` and the dotted name to import `path` by.

One browser tab’s run: build, step, profile, record, scrub and replay a model.

`StudioSession` holds no widget: the Solara app calls it and redraws from what it holds, and the tests drive it directly. Every method that changes the run takes `lock`, so the play loop’s thread and the widgets’ callbacks never see a half-made step.

#### `class StudioSession(model_class: type[Model], config: StudioConfig, agent_portrayal: Callable | None = None)`

The state of one Studio run, independent of the widgets that show it.

**Parameters:**

- **model_class** – The model to run.
- **config** – The Studio settings.
- **agent_portrayal** – How the space view draws agents; one colour per class when None.

Build the first run with the default parameters and `config.seed`.

#### `property shown: Model`

the scrubbed-to state, else the live model.

**Type:**

The model the views show

#### `property replaying: bool`

Whether scrubbing reruns the model instead of restoring checkpoints.

#### `say(message: str) → None`

Add a line to the run log.

#### `reset() → None`

Rebuild the model from the panel’s values and seed, at step 0.

#### `step(n: int = 1) → int`

Advance the live model `n` steps (fewer if it stops); the steps taken.

#### `scrub(step: float) → None`

Show the run at `step`; at or past the live step, show the live model.

#### `replay() → None`

Make the scrubbed-to state the live run, with the panel’s changed values.

#### `profile_report(top: int = 15) → str`

The profiler’s report over the last `config.profile_steps` steps.

#### `source_file() → Path | None`

The file the lint panel checks: the target’s, else the class’s source.

#### `lint() → list[modelly.lint.Finding]`

The `modelly lint` findings of the model’s file.

The run Studio’s scrubber moves through: checkpoints when the model allows, else replay.

`track` records a model with a `modelly.timetravel.Recorder`: scrubbing restores a checkpoint, instantly. A model that cannot be checkpointed (it holds a lambda, say) gets a `ReplayTimeline` instead: the same `steps` / `span` / `at` interface, where `at` rebuilds the model from the start of the run and runs it on to the step. Seeded runs are reproducible, so the state is the same; it only takes longer.

#### `class ReplayTimeline(start: Callable[[], Model], live: Model)`

A timeline for a model that cannot be checkpointed: `at` reruns from the start.

**Parameters:**

- **start** – Returns a new model in the state the run started from.
- **live** – The model being run; the span ends at its current time.

Follow `live`, which started as `start()` returns.

#### `property steps: list[float]`

Only the start of the run is held.

#### `property span: tuple[float, float]`

From the start of the run to the live model’s time.

#### `at(step: float) → Model`

A new model at `step`: the run rebuilt and run on to `step`.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If `step` is outside `span`.

#### `stop() → None`

Nothing to stop: a replay timeline does not hook the model.

#### `track(model: Model, start: Callable[[], Model], every: float, budget: int) → tuple[Timeline, str | None]`

Record `model`: a `Recorder` when it can be checkpointed, else a replay.

**Returns:**

The timeline and, when it is a replay, the reason checkpoints were not possible.

What Studio’s views and exports read from a model: series, agents, figures, files.

Plain functions of a model, so that the views, the exports and the tests share them.

#### `model_series(model: Model) → pd.DataFrame | None`

The numeric model reporters the `DataCollector` collected, or None.

#### `series_figure(model: Model) → Figure | None`

A line plot of every numeric model reporter, or None when there is none.

#### `agent_classes(model: Model) → list[str]`

`All` and the names of the agent classes present, sorted.

#### `agent_table(model: Model, class_name: str = 'All', rows: int = 100) → pd.DataFrame`

The first `rows` agents (of `class_name`) by `unique_id`, one column per attribute.

#### `figure_bytes(figure: Figure, fmt: str) → bytes`

`figure` saved as `png` or `svg`.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – For another format.

#### `series_image(model: Model, fmt: str = 'png') → bytes | None`

The reporters plot as an image file, or None when nothing was collected.

#### `space_image(session: StudioSession, fmt: str = 'png') → bytes | None`

The space view as shown, as an image file, or None when there is no space.

#### `parquet_available() → bool`

Whether pyarrow is installed, so the data can be exported as Parquet.

#### `data_bytes(model: Model, fmt: str = 'csv') → bytes | None`

The collected model data as `csv` or `parquet`, or None when none was collected.

#### `checkpoint_file(model: Model) → bytes`

The model as a `Model.load` checkpoint.

**Raises:**

[**CheckpointError**](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.CheckpointError) – When the model holds something that cannot be saved.

#### `timeline_steps(span: tuple[float, float]) → list[float]`

The steps an animation of `span` shows: every step, sampled to `MAX_FRAMES`.

#### `replay_frames(timeline, steps: list[float]) → Iterator[Model]`

One model restored at the first step and run on through `steps`.

#### `animation_bytes(session: StudioSession, suffix: str = '.gif') → bytes | None`

The recorded run’s space view as a GIF or MP4, or None when there is no space.

A Studio session as a Python script that rebuilds its live run.

Studio records what makes the live run what it is: each new run (the panel’s values and the seed it was built with) and each replay from a scrubbed-to step (the Scenario values changed and, when it changed, the seed). Steps are counted from the model’s time, which every step advances by one. Scrubbing alone leaves the live run as it was, so it is not recorded; a replay cuts the steps after the step it starts from.

`SessionRecording.script(time)` writes the record as a plain Python script: it builds the model as Studio did, steps it, applies each replay’s changes at its step, and ends with the model in the state the live run had at `time`. Checkpoints restore a run bit for bit, so replaying from a step and stepping on to it give the same state, and the script needs no checkpoint file.

#### `class Segment(kind: str, values: dict[str, Any], seed: int | None, start: float = 0.0, steps: int | None = None)`

One stretch of the live run: how it began and the time it began at.

**Variables:**

- **kind** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – `new run` (the model was built) or `replay` (a scrubbed-to state with changed values became the live run).
- **values** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]*) – For a new run, every value the model was built with; for a replay, the Scenario values it changed.
- **seed** ([*int*](https://docs.python.org/3/builtins/functions.html#int)* | **None*) – The seed a new run was built with, or the seed a replay reseeded with (None when a replay kept the generators as they were).
- **start** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – The model’s time when the stretch began.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)* | **None*) – The steps taken in it, set when a later replay cuts it short.

#### `class SessionRecording(target: str)`

What a Studio session did to its live run, and the script that does it again.

**Parameters:**

**target** – The `path/to/model.py:Class` or `module:Class` Studio was started on.

Start an empty record for `target`.

#### `new_run(values: dict[str, Any], seed: int, time: float = 0.0) → None`

A model built with `values` and `seed` became the live run.

#### `replayed(time: float, changes: dict[str, Any], seed: int | None) → None`

The state at `time` became the live run, with `changes` and `seed` applied.

#### `property straight: bool`

Whether the live run is one new run stepped on, with no replay in it.

#### `body(time: float) → list[str]`

The source lines of `replay()`’s body, for a live run now at `time`.

#### `script(time: float, name: str = 'the model', filename: str = 'session.py') → str`

The Python script that rebuilds the live run, now at `time`.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – When nothing was recorded yet.

#### `literal(value: Any) → str`

`value` as Python source: a literal, or an Enum member looked up by name.

Files that let someone else rerun what Studio showed: the session script and a bundle.

`session_script` is the Python script of the session’s live run (see `modelly.studio.recording`). `bundle_bytes` runs the live run again with `modelly run`’s recorder and packs it with `modelly bundle`: a zip with the manifest, the outputs, the model code, the seeds and the lock file, which `modelly verify` checks. A manifest records one run built from its parameters and stepped on, so a live run that came from Replay from here has a script but no bundle.

#### `bundle_bytes(session: StudioSession) → bytes`

The live run rerun, recorded and packed as a `modelly bundle` zip.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – When the live run came from a replay.

#### `bundle_spec(session: StudioSession, out: Path) → RunSpec`

The `modelly run` of the live run: its values and seed, as many steps as it took.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – When the live run came from a replay (see `NOT_STRAIGHT`).

#### `script_name(session: StudioSession) → str`

The file name the session script downloads as.

#### `session_script(session: StudioSession) → bytes`

The Python script that rebuilds the session’s live run, as UTF-8 bytes.

Replicates of the session’s model, and the bands across them over time.

`ensemble_of` builds a `modelly.stream.Ensemble` of the parameter panel’s values: each replicate gets a seed spawned from the panel’s seed, as `Scenario.spawn_replications` hands them out. `reporter_operator` reads the DataCollector’s numeric model reporters from a replicate, so the bands and the filters need nothing written for Studio. `band_series` steps the ensemble and stacks `Ensemble.band` at every step: the long-format frame (`time`, `quantity`, `mean`, `q0.05`, `q0.5`, `q0.95`) the ensemble view draws. It steps the replicates themselves, so it works for models that cannot be checkpointed too.

#### `exception NoReportersError`

The model collects no numeric model reporter for a band or a filter to read.

#### `band_series(ensemble: Ensemble, steps: int, operator: ObservationOperator | None = None, quantiles: Sequence[float] = (0.05, 0.5, 0.95)) → DataFrame`

The band of `operator` now and after each of `steps` steps, stacked.

`operator` defaults to the first replicate’s numeric model reporters. The replicates are stepped in place.

#### `ensemble_of(session: StudioSession, replicates: int, prior: Prior | None = None) → Ensemble`

`replicates` models with the panel’s values, seeds spawned from the panel’s seed.

#### `factory_and_scenario(model_class: type[Model], values: dict[str, Any], seed: int) → tuple[Callable[..., Model], Scenario]`

What `Ensemble` builds replicates with: a factory and the scenario to replicate.

Constructor keywords go to the factory, the other values to the model’s Scenario class; a model without one gets a plain `Scenario` that carries the seed.

#### `latest_value(name: str, model: Model) → float`

The last value the model’s DataCollector collected for `name`; NaN before any.

#### `reporter_operator(model: Model) → ObservationOperator`

An observation operator over the model’s numeric model reporters.

**Raises:**

[**NoReportersError**](https://remipelloux.github.io/Modelly/dev/apis/studio.html#modelly.studio.ensembles.NoReportersError) – When the model collects none.

#### `session_bands(session: StudioSession, replicates: int = 20, steps: int = 50) → pd.DataFrame`

The band of the model reporters across `replicates` new runs of the panel’s values.

Data assimilation from Studio: a particle filter or an ensemble Kalman filter, traced.

`assimilate` runs one of the `modelly.stream` filters over an ensemble of the session’s model against a table of observations (a CSV file with a `time` column and one column per observed reporter), and keeps what the dashboard shows at every observation:

- `bands`: the filtered band of every reporter (the long-format frame of `Ensemble.band`);
- `history`: the filter’s own history: the effective sample size, whether it resampled and the log evidence for the particle filter; each parameter’s mean and spread for the ensemble Kalman filter;
- `weights`: for the particle filter, each replicate’s weight once the observation is taken into account, before any resampling (one row per observation, one column per replicate).

The weights are those the filter computes (prior weight times Gaussian likelihood, normalised); they are read before `assimilate` resamples, so the trace shows the degeneracy the effective sample size measures.

#### `class Assimilation(method: str, bands: DataFrame, history: DataFrame, observations: DataFrame, weights: DataFrame = <factory>)`

What one filter run left: the bands, its history and the weights over time.

#### `class FilterSettings(method: str = 'particle filter', replicates: int = 20, sd: float = 1.0, threshold: float = 0.5, parameters: tuple[str, ...] = (), spread: float = 0.5)`

How Studio assimilates the observations.

**Variables:**

- **method** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – `particle filter` or `ensemble Kalman filter`.
- **replicates** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – The ensemble size.
- **sd** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – The observation error, one standard deviation for every quantity.
- **threshold** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – The particle filter resamples when the ESS falls below this fraction of the ensemble size.
- **parameters** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – The model attributes the ensemble Kalman filter adjusts.
- **spread** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – Each adjusted attribute starts uniform within this fraction of its value.

#### `adjustable(session: StudioSession) → list[str]`

The live model’s float attributes, but its clock: what the Kalman filter can adjust.

#### `assimilate(session: StudioSession, observations: Sequence[sources.Observation], settings: FilterSettings | None = None) → Assimilation`

Run the filter `settings` names over `observations`, from the panel’s values.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – For an unknown method, no observations, or a Kalman filter with no parameter to adjust.

#### `kalman_prior(session: StudioSession, settings: FilterSettings) → dict`

A uniform start within `spread` of each adjusted attribute’s live value.

#### `observation_frame(observations: Sequence[Observation]) → DataFrame`

The observations long-format: one row per time and quantity (`value`).

#### `posterior_weights(pf: ParticleFilter, observation: Observation) → ndarray`

The weights `pf` gives its replicates for `observation`, before resampling.

#### `read_observations(path: str | Path) → list[Observation]`

Every observation of a CSV file with a `time` column, in time order.

Browse an experiment’s results store: its runs, filtered by parameters, one output against one.

`ExperimentBrowser(path)` opens the folder an `Experiment` wrote (`experiment.json` and one Parquet file per run, see `modelly.experiments.store`). `runs()` has one row per finished run: its keys, its parameters and its outputs at its last step. `select` keeps the runs whose parameters fall in a range or a set of values; `against` summarises an output over the runs at each value of a parameter, which the Experiments tab plots; and `series` gives the selected runs’ outputs step by step.

Needs the `experiments` extra (pyarrow and DuckDB), like the store itself.

#### `class ExperimentBrowser(path: str | Path)`

The runs of one results store, for the Experiments tab.

**Parameters:**

**path** – The store folder.

**Raises:**

[**LookupError**](https://docs.python.org/3/builtins/exceptions.html#LookupError) – When the folder holds no finished run.

Open the store’s runs as a DuckDB view.

#### `runs() → DataFrame`

One row per finished run: keys, parameters and the outputs at its last step.

#### `select(selection: Mapping[str, tuple[float, float] | Sequence[Any]] | None = None) → DataFrame`

The runs whose parameters `selection` allows.

`selection` maps a parameter to a `(low, high)` range (both ends kept) or to a list of the values to keep; parameters it does not name are not filtered.

**Raises:**

[**KeyError**](https://docs.python.org/3/builtins/exceptions.html#KeyError) – When it names a column the runs do not have.

#### `against(parameter: str, output: str, runs: DataFrame | None = None) → DataFrame`

`output` at the runs’ last step, summarised at each value of `parameter`.

One row per value, sorted, with the mean, min, max and count over the runs (all of them unless `runs`, a selection, is given).

#### `series(output: str, run_ids: Sequence[str] | None = None) → DataFrame`

`output` step by step, one column per run (all runs unless `run_ids`).

#### `describe() → str`

A line for the tab: the model, the run count, the parameters and the outputs.

Calibration posteriors and sensitivity results, as the Analysis tab shows them.

`modelly studio model.py:Model --analysis analysis.py:results` names a function that returns what to show: a `modelly.calibrate.Posterior`, a `modelly.sensitivity.SensitivityResult` (Morris, Sobol, PAWN, OAT), or a list or dict of them. The function runs once, when the tab first opens; it can load a saved calibration, read a results store or run a quick analysis. From Python, append the objects to `StudioSession.analyses`.

`view_of` turns one object into what the tab draws: a title, its own figure (the posterior’s marginals, pairs and fits; the sensitivity method’s plot) and a table (the posterior summary with highest-density intervals; the ranked indices).

#### `class AnalysisView(title: str, kind: str, figure: Callable[[], Any], table: DataFrame)`

What the Analysis tab shows for one result.

#### `as_list(found: Any) → list[tuple[str, Any]]`

`(name, result)` pairs from one result, a list of them or a dict of them.

#### `load_analyses(target: str) → list[tuple[str, Any]]`

Call the function `path/to/file.py:function` names; its results, named.

**Raises:**

**TargetError** – When the function cannot be found.

#### `view_of(name: str, result: Any) → AnalysisView`

The title, figure and table of a posterior or a sensitivity result.

**Raises:**

[**TypeError**](https://docs.python.org/3/builtins/exceptions.html#TypeError) – For anything else.

Matplotlib figures of Studio’s ensemble, assimilation and experiment views.

Plain functions of DataFrames, built on `matplotlib.figure.Figure` (no pyplot state), so the views, their exports and a script share them:

- `band_figure`: a band frame (`time`, `quantity`, `mean`, `q<level>` columns, as `modelly.stream` ensembles and filters return) with the observations on top;
- `ess_figure` and `weights_figure`: a particle filter’s effective sample size and its replicates’ weights over time;
- `trajectory_figure`: the parameters an ensemble Kalman filter adjusted, mean and spread;
- `against_figure` and `series_figure`: an experiment’s output against a parameter, and its runs step by step.

#### `against_figure(runs: DataFrame, summary: DataFrame, parameter: str, output: str) → Figure`

Every run’s `output` against its `parameter` value, the mean per value on top.

#### `band_figure(bands: DataFrame, observations: DataFrame | None = None) → Figure | None`

One panel per quantity: its band over time, the observed values as dots.

`observations` is long-format too (`time`, `quantity`, `value`). None when `bands` is empty.

#### `band_levels(bands: DataFrame) → list[float]`

The quantile levels a band frame has columns for, lowest first.

#### `ess_figure(history: DataFrame, replicates: int, threshold: float) → Figure`

The effective sample size at each observation, the resampling threshold dotted.

#### `series_figure(series: DataFrame, output: str) → Figure`

One line per run: `output` step by step.

#### `trajectory_figure(history: DataFrame, parameters: Sequence[str]) → Figure`

Each adjusted parameter’s ensemble mean over time, one standard deviation shaded.

#### `weights_figure(weights: DataFrame) → Figure`

Each replicate’s weight at each observation, as a heat map (darker is heavier).

What the Map tab draws: agents as points, network edges and region outlines as lines.

`scene_of(model)` reads the model’s space into flat arrays a WebGL (or Canvas 2D) renderer uploads as they are:

- `points`: one `(x, y)` per agent: its position in a continuous or geographic space, else its cell’s position (a network node’s layout position, a grid cell’s coordinate);
- `classes`: each point’s agent class, an index into `legend` (one Okabe-Ito colour per class, in name order);
- `nodes`: a network’s nodes, drawn small and grey under the agents;
- `segments`: `(x0, y0, x1, y1)` per line: a network’s edges, a `GeoSpace`’s region outlines.

Coordinates are shifted so the space’s lower-left corner (a continuous space’s ranges, a grid’s first cell, else the lowest node or agent) is the origin: projected metres (six or seven digits) lose no precision in the renderer’s 32-bit floats that way, and the view does not jump as agents move. `encode` packs the arrays as base64 little-endian buffers for the browser.

#### `class Scene(points: ~numpy.ndarray, classes: ~numpy.ndarray, legend: list[tuple[str, str]], nodes: ~numpy.ndarray = <factory>, segments: ~numpy.ndarray = <factory>, origin: tuple[float, float] = (0.0, 0.0), extent: tuple[float, float] = (1.0, 1.0), colours: ~numpy.ndarray | None = None)`

Flat arrays of one model state, in coordinates shifted to start at `origin`.

#### `property size: int`

How many points, nodes and lines the scene holds.

#### `element_count(model: Model) → int`

Agents plus network edges: what drawing the model’s space costs, roughly.

#### `encode(scene: Scene) → dict[str, Any]`

The scene as the browser reads it: base64 buffers, counts, extent and palette.

#### `portrayal_colours(agents: list, portrayal: Callable) → ndarray`

Each agent’s portrayal colour as RGBA bytes; an agent it returns None for is hidden.

#### `scene_of(model: Model, portrayal: Callable | None = None) → Scene | None`

The scene of `model`’s space, or None when it has no space.

With a `portrayal` and at most `PORTRAYAL_LIMIT` agents, each point takes its portrayal’s colour; otherwise each class has its colour.

Solara’s front-end files, cached once so Studio runs with no network.

Solara’s page loads its JavaScript, CSS and fonts through a proxy of the jsDelivr CDN on the Studio server (`/_solara/cdn/...`): the first request for a file downloads it into a cache folder (`share/solara/cdn` in the environment, or `SOLARA_ASSETS_PROXY_CACHE_DIR`) and later ones are served from there, so the browser itself never leaves localhost. A machine without internet access needs the cache filled beforehand:

```default
python -m modelly.studio.assets            # list what is cached and what is missing
python -m modelly.studio.assets --fetch    # download what is missing (once, online)
```

The files are those Solara’s page template names (the Vuetify app, its fonts, RequireJS, Font Awesome) and the files their style sheets point to (the icon and text fonts). The `solara-assets` package that used to ship them lags behind Solara’s releases, so Studio does not rely on it. Copying the cache folder to another machine with the same Solara works too. Studio’s own code (the map’s WebGL renderer included) ships inside Modelly.

#### `cache_folder() → Path`

The folder Solara’s CDN proxy caches files in.

#### `page_assets() → list[str]`

The CDN paths Solara’s page template loads, for this Solara and ipywidgets.

#### `style_references(path: str, css: str) → list[str]`

The files the style sheet at CDN `path` points to, as CDN paths.

#### `required_assets(folder: Path | None = None) → list[str]`

The page’s files, and the files the cached style sheets among them point to.

#### `missing_assets(folder: Path | None = None) → list[str]`

The files Studio’s page needs that are not in the cache yet.

#### `fetch_assets(folder: Path | None = None) → list[str]`

Download every missing file into the cache (style sheets first); those fetched.

#### `warning(folder: Path | None = None) → str | None`

The line `modelly studio` prints when files are missing, else None.

#### `main(argv: list[str] | None = None) → int`

List the cached and missing files; with `--fetch`, download the missing ones.

The Map tab: the model’s space drawn by WebGL in the browser, for large models.

`MapWidget` is a Vue template (`map.vue`, shipped with Modelly: nothing comes from a CDN) that uploads the arrays of `modelly.studio.scene` to the GPU and draws agents as points, network edges and region outlines as lines, with pan and zoom. Where WebGL is not available, the same template draws with Canvas 2D; the checkbox under the map forces that.

#### `class MapWidget(*args: t.Any, **kwargs: t.Any)`

The WebGL map: draws an `encode`-d scene, pans and zooms in the browser.

Public constructor

The Studio page: the layout of the panels, and `Page`, which the server shows.

`StudioApp(session)` is the whole app for one session, which the tests render headless. `Page` is what `modelly studio` serves: it reads the `StudioConfig` from the environment, loads the model class once per server, and gives each browser tab a session.

#### `new_session(config: StudioConfig) → StudioSession`

A session for one browser tab.

## Studio for everyone, languages and classrooms

Comparing scenarios in Studio, without code: the session’s model, several parameter sets.

`compare_scenarios(session, scenarios, output)` runs each scenario (a name and the parameters it changes from the panel’s values) `replicates` times on common random numbers, with `modelly.decide.compare`, and reads `output`, a model reporter, at the end of each run. The Compare tab shows the ranking with intervals and each scenario’s paired difference from the first.

#### `reporters(session: StudioSession) → list[str]`

The model reporters of the session’s model, the outputs a comparison can read.

#### `final_value(model: Any, output: str) → float`

The last collected value of the model reporter `output`.

#### `compare_scenarios(session: StudioSession, scenarios: Mapping[str, Mapping[str, Any]], output: str, *, steps: int = 50, replicates: int = 10, seed: int | None = None) → Comparison`

Each scenario’s `output` after `steps` steps, `replicates` times, paired.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – for an output that is not a model reporter, or fewer than two scenarios.

A report of a Studio session, to hand to someone who will not open Studio.

`report_html(session)` is one self-contained HTML file (figures embedded as PNG): the model, its parameters and seed, a figure of every model reporter, their final values, the comparison of scenarios when there is one, the model card when the model has one, and the run’s manifest (Modelly and Python versions, the digest of the model’s source, the steps run), so a reader knows exactly which run the numbers come from. `report_pdf` holds the same, one figure per page.

#### `card_path(target: str) → Path | None`

The model card of `target`: `card.toml` next to its file, or its zoo card.

#### `manifest(session: StudioSession) → dict[str, str]`

Which run the report shows: versions, model, source digest, seed and steps.

#### `series_figures(session: StudioSession) → list[tuple[str, bytes]]`

One PNG per model reporter: its series over the run.

#### `markdown_html(text: str) → str`

The Markdown of a model card as HTML: headings, lists, tables, paragraphs.

#### `report_html(session: StudioSession, comparison: Comparison | None = None, output: str | None = None) → str`

The session’s report as one HTML document.

#### `pdf_lines(session: StudioSession) → list[str]`

The text of the PDF report: title, parameters, manifest, card.

#### `report_pdf(session: StudioSession, lines_per_page: int = 50) → bytes`

The parameters, manifest and card as text pages, then one page per figure.

The Studio tabs for people who do not write code: compare, the model card, the builder.

- `CompareTab`: pick a reporter, a parameter and the values to try; Studio runs each value on common random numbers (`modelly.studio.compare`) and shows the ranking with intervals and the differences from the first value.
- `CardTab`: the model card, when the model has one.
- `BuilderTab`: a form over `modelly.new.builder`; it shows the model’s code and downloads it.

`report_downloads` adds the HTML and PDF reports to the Export panel. With `modelly studio --no-code` only these tabs and the views stay (`NO_CODE_TABS`).

#### `parse_values(text: str) → list[Any]`

`"0.1, 0.2, 0.3"` as Python values; a value that is not a literal stays a string.

#### `comparison_rows(comparison: Any, output: str) → list[dict[str, Any]]`

The table the Compare tab shows: one row per scenario, best first.

#### `run_comparison(session: Any, parameter: str, text: str, output: str, steps: int, replicates: int) → tuple[list[dict[str, Any]] | None, str]`

The Compare tab’s table and message for `parameter` set to each value of `text`.

#### `report_downloads(state: Any, stamp: str) → list[tuple]`

`(make the bytes, file name, label)` of the HTML and PDF reports.

Studio in other languages: every label through `t`, catalogs per language, right to left.

Each label Studio shows is written in English and passed through `t(text)`, which returns its translation in the session’s language (`modelly studio --language fr`) from `modelly/studio/locales/<language>.json`, or the English text when the catalog has none. A language written right to left (Arabic, Hebrew, Persian, Urdu) also turns the page’s direction, so panels, tables and text line up from the right.

The catalogs are keyed by the English text. `tests/studio/test_studio_i18n.py` extracts every `t("...")` from the code and checks that each shipped catalog translates exactly those, so a new label without its translations fails the tests.

#### `languages() → list[str]`

English and every language with a catalog, sorted.

#### `supported() → list[str]`

The languages `--language` takes: the catalogs, and the right-to-left ones.

#### `catalog(language: str) → dict[str, str]`

The translations of `language`, keyed by the English text; empty for English.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – for a language with no catalog.

#### `set_language(language: str) → None`

Translate the labels rendered from now on, in this context, into `language`.

#### `language() → str`

The language labels are rendered in.

#### `t(text: str) → str`

`text` in the current language, or as it is when there is no translation.

#### `direction(language_code: str | None = None) → str`

`"rtl"` for a language written right to left, `"ltr"` otherwise.

Studio’s accessibility layer (WCAG 2.2 AA), on top of Solara’s page.

Solara’s page template disables zooming and sets no language; Vuetify’s sliders, icon buttons and the plots’ images carry no accessible names, and its field labels are lighter than a 4.5:1 contrast. `modelly/templates/index.html.j2`, which Solara finds before its own template, re-enables zooming, raises the labels’ contrast, shows a visible focus ring, and runs a small script that names every unnamed slider (by its field’s label), icon button (by its icon) and image (by its card’s title) as they appear, and sets the page’s language and direction from `LanguageMarker`. `tests/studio/test_studio_a11y.py` runs axe-core on the served page and on the documentation and fails on any WCAG A or AA violation.

Classroom mode: an instructor shares parameters, students submit runs, everyone sees them.

`modelly studio model.py:Model --classroom DIR` points every student’s Studio at one folder (a shared drive, a synced folder, or one machine serving the whole class). In it:

- `parameters.json`: the values the instructor shared (`share`), which every new session starts from;
- `runs/`: one JSON file per submitted run (`submit`): who, the parameter values, the seed, the steps run and the final value of every model reporter.

The Classroom tab shows every submission as a table, so the class can compare its runs (`submissions`). Files are written to a temporary name and renamed, so a half-written file is never read.

#### `shared_values(folder: str | Path) → dict[str, Any]`

The parameters the instructor shared; empty when none were.

#### `share(session: StudioSession, folder: str | Path) → Path`

Share the session’s parameter values with the class.

#### `submit(session: StudioSession, folder: str | Path, student: str) → Path`

Save the live run for the class: who, the values, the seed, the steps, the results.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – without a name.

#### `submissions(folder: str | Path) → DataFrame`

Every submitted run, oldest first: student, seed, steps, values and results.

The Classroom tab: submit this run, share these parameters, see the class’s runs.
