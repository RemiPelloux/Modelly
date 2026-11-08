# Web

Modelly in the browser: `modelly export-web` and the Python its pages run in Pyodide. How to use it is in [Modelly in the browser](https://remipelloux.github.io/Modelly/dev/browser.html).

Module

Contents

modelly.web.export

WebExport, export_web, PYODIDE_VERSION

modelly.web.packages

the Pyodide packages a model needs

modelly.web.wheel

the pure-Python wheel a site ships

modelly.web.runtime

BrowserRun, what the page’s Web Worker calls

modelly.web.snapshot

the series and agent places the page draws

`export_web`: write a static site that runs a model in the browser with Pyodide.

The site is plain files, deployable on GitHub Pages or any static host:

```default
index.html, app.js, draw.js, worker.js, style.css   the runner page
modelly.json                                         what to load and run
wheels/modelly_abm-<version>-py3-none-any.whl        Modelly, pure Python
model.zip                                            the model's code, unless it is
                                                     part of Modelly (an example, a
                                                     zoo model)
```

Pyodide itself comes from its CDN at the pinned `PYODIDE_VERSION`, with only the packages the model was seen to import (`modelly.web.packages`).

#### `class WebExport(target: str, out: Path, steps: int = 100, seed: int = 42, title: str = '', wheel: Path | None = None, pyodide_url: str = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/', add_packages: tuple[str, ...] = (), skip_packages: tuple[str, ...] = ())`

What `export_web` writes.

**Variables:**

- **target** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The model, `path/to/model.py:Class` or `package.module:Class`.
- **out** ([*pathlib.Path*](https://docs.python.org/3/library/pathlib.html#pathlib.Path)) – The folder the site is written to (created; files in it are replaced).
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – The steps the export runs the model for, to check it and to see what it imports; also the page’s default run length.
- **seed** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – The seed of that run and the page’s default seed.
- **title** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The page title; the model class name when empty.
- **wheel** ([*pathlib.Path*](https://docs.python.org/3/library/pathlib.html#pathlib.Path)* | **None*) – A Modelly wheel to ship instead of the pure one built from this install, such as one built for WebAssembly with `pyodide build`.
- **pyodide_url** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – Where the page loads Pyodide from (the pinned CDN release).
- **add_packages** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – Pyodide packages to load in addition to the detected ones.
- **skip_packages** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – Detected packages not to load.

#### `export_web(options: WebExport) → dict[str, Any]`

Write the static site `options` describes; the manifest it wrote.

**Raises:**

**TargetError** – When the model cannot be found, built or run for `steps` steps.

#### `model_code(target: str) → ModelCode`

The import name of `target`’s module and the files the site needs for it.

The Pyodide packages a model needs: the ones its import and its first steps load.

`python -m modelly.web.packages TARGET STEPS SEED` builds the model in a fresh interpreter, runs it, and prints the distributions of the third-party modules imported after `import modelly` as JSON. `needed_packages` runs it in a subprocess, so what the exporting process imported before does not count. `import modelly` itself needs only `CORE` in the browser; the page loads nothing else, so an optional dependency the model does not use (matplotlib for networkx, pyarrow for pandas) is not downloaded.

#### `exception ModelRunError`

The model was found but raised while it was built or run.

#### `distributions_of(modules: set[str]) → set[str]`

The installed distributions that provide `modules`, stdlib and Modelly excluded.

#### `needed_packages(target: str, steps: int, seed: int) → list[str]`

`probe` in a fresh interpreter.

**Raises:**

[**ModelRunError**](https://remipelloux.github.io/Modelly/dev/apis/web.html#modelly.web.packages.ModelRunError) – When the model cannot be imported, built or run.

#### `normalise(name: str) → str`

A distribution name as Pyodide’s lock file spells it (PEP 503).

The pure-Python wheel of Modelly a static site ships for Pyodide.

`write_wheel` packs the installed `modelly` package, without its compiled modules (the pure-Python twins replace them), its C sources and the parts that cannot run in a browser tab or that a model does not import (`EXCLUDED`: the command-line tools, Solara visualisation, the examples). An example model’s own folder is kept, so an exported example finds its code. The wheel is deterministic: same files, same bytes.

#### `package_files(keep: PurePosixPath | None = None) → list[PurePosixPath]`

The package’s files the wheel holds, relative to its root, sorted.

**Parameters:**

**keep** – A folder under an excluded part (`examples/basic/schelling`) to keep.

#### `wheel_name(version: str = '1.5.1') → str`

The file name of the browser wheel of `version`.

#### `write_wheel(out_dir: Path, keep: PurePosixPath | None = None) → Path`

Write the browser wheel into `out_dir`; its path.

The Python half of the browser runner: what the page’s Web Worker calls in Pyodide.

`BrowserRun` builds the model from the parameter panel’s values, advances it a few steps at a time and reports what the page draws. Values cross the JavaScript boundary as JSON strings, so the worker never holds a Python object but the run itself.

The panel’s fields are Studio’s (`modelly.studio.params`), encoded for the page by `encode_parameter`: a `choice` sends the index of the selected value, a `fixed` field is shown as its `repr` and keeps its default.

#### `class BrowserRun(target: str)`

One model in a browser tab, rebuilt by `build` and advanced by `advance`.

Load the model class `target` names (`package.module:Class`).

#### `build(values_json: str, seed: int) → None`

A new model from the panel’s `values` (JSON, by name) and `seed`.

#### `advance(steps: int, budget_s: float = 0.05) → int`

Up to `steps` steps, fewer when the time budget ends or the model stops.

#### `state_json(colour_by: str = 'class') → str`

The page’s view of the run: time, the new reporter rows and the space.

#### `decode_value(parameter: Parameter, raw: Any) → Any`

The value the page sent for `parameter`, as the model takes it.

#### `describe(model_class: type) → list[dict[str, Any]]`

The parameter panel of `model_class`, encoded for the page.

#### `encode_parameter(parameter: Parameter) → dict[str, Any]`

`parameter` as the JSON the page builds its field from.

#### `native_modules() → list[str]`

The compiled `modelly._native` modules this interpreter can import.

What the browser runner draws: the agents’ places in space and the model reporters.

Plain functions of a model that return JSON-ready values, so the page’s space view and plot read the same data in Pyodide and the tests read it in CPython.

#### `colour_attributes(model: Model) → list[str]`

The numeric attributes of the agents the space view can colour by, sorted.

#### `series_rows(model: Any, start: int = 0) → dict[str, list] | None`

The numeric model reporters collected from row `start` on, by name, or None.

#### `space_view(model: Model, colour_by: str = 'class') → dict[str, Any] | None`

The agents’ places and colour values, or None when no agent has a place.

Each point is `[x, y, value]`: the index of the agent’s class name in `classes` when `colour_by` is `class`, else the agent’s `colour_by` attribute (None when it has none). `cells` tells the page to draw grid squares instead of dots.
