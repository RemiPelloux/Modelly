# Modelly in the browser

`modelly export-web` turns a model into a static web page that runs it in the reader's
browser: no installation, no Python on their machine, no server code. Python, Modelly and
the model run in the tab with [Pyodide](https://pyodide.org/), CPython compiled to
WebAssembly. Put the folder on GitHub Pages, in your docs, or on any static host, and share
the link. The [gallery](gallery.md) embeds three such pages.

```bash
modelly export-web model.py:Epidemic --out site/
python -m http.server --directory site 8000     # then open http://localhost:8000
```

Browsers do not run the page from `file://` (it starts a Web Worker and fetches files), so
open it through a web server, even locally.

## What the page does

The page has the same parameter panel as [Studio](studio.md), built from the model's
`Scenario` and its constructor's keyword arguments: sliders for fractions, number and text
fields, selects for `Literal` and `Enum` fields, checkboxes for booleans, and the seed.
Reset builds the model, Step and Run advance it, Stop interrupts a run. The model runs in a
Web Worker, a few steps at a time (about 50 ms of work per slice), so the page stays
responsive during long runs and Stop takes effect after the current slice. Two views show
the run: the agents in space (grid cells, continuous positions or network nodes, coloured by
class or by a numeric attribute) and the numeric model reporters of the `DataCollector`
over time.

`?lazy=1` at the end of the page's URL waits for a click on Start before downloading
anything, which is what an embedded page should do.

## What the export writes

```text
site/
  index.html app.js draw.js worker.js style.css   the page
  modelly.json                                     what to load and run
  wheels/modelly_abm-<version>-py3-none-any.whl    Modelly, pure Python
  model.zip                                        the model's code (not for an example
                                                   or a zoo model, which the wheel holds)
```

Pyodide itself comes from its official CDN (`cdn.jsdelivr.net/pyodide`) at the version
`modelly.web.PYODIDE_VERSION` pins (314.0.7, Python 3.14); `--pyodide-url` points the page
at another copy, such as a self-hosted one.

The export first runs the model for `--steps` steps (default 100) in a fresh Python process,
to check it builds and runs, and to see which third-party packages it imports. The page
loads exactly those from Pyodide, plus numpy and pandas, and nothing they merely list as
dependencies: a network model loads networkx and scipy but not matplotlib. `--package NAME`
adds a package the check run did not reach, `--skip-package NAME` drops one.

The shipped wheel holds Modelly without the parts a browser model does not import: the
command-line tools, the Solara visualisation, the examples other than the exported one, and
the C sources. Its compiled modules are replaced by their pure-Python twins, which give the
same results (see [Determinism](determinism.md)).

| Option | Meaning |
|---|---|
| `--out DIR` | the site folder (default `site/`) |
| `--steps N` | the check run's length and the page's default run length |
| `--seed S` | the check run's seed and the page's default seed |
| `--title T` | the page title (default: the class name) |
| `--wheel PATH` | ship this Modelly wheel instead, such as the WebAssembly one below |
| `--pyodide-url URL` | where the page loads Pyodide from |
| `--package NAME`, `--skip-package NAME` | edit the list of Pyodide packages |

The same from Python:

```python
from pathlib import Path

from modelly.web import WebExport, export_web

export_web(WebExport("model.py:Epidemic", Path("site"), steps=50))
```

## Compiled modules in WebAssembly

The four C modules of `modelly/_native` (`fastrng`, `fastloop`, `fastcell`, `fastset`) also
build for WebAssembly with Emscripten, through `pyodide build`:

```bash
pip install pyodide-build                       # with Python 3.14, Pyodide 314's version
pyodide xbuildenv install 314.0.7
pyodide xbuildenv install-emscripten
bash scripts/build-wasm-wheel.sh                # writes dist/wasm/modelly_abm-...-wasm32.whl
modelly export-web model.py:Epidemic --out site/ --wheel dist/wasm/modelly_abm-*.whl
```

The page footer says which version runs: "pure Python" or "compiled: fastrng, fastloop,
fastcell, fastset". The compiled wheel is the whole package (it is not trimmed), about
830 KB against about 520 KB for the pure one, and the CI job `browser` runs every example
with both.

## What runs in the browser

Every example of `modelly/examples` and every zoo model runs from its static export in a
headless Chromium, with the pure wheel and with the compiled one
(`tests/web/test_browser.py`, opt-in with `MODELLY_BROWSER_TESTS=1`; the hosted `browser`
job runs it). That includes the language-model example (its replay client answers offline;
in Pyodide the calls go one at a time, since threads cannot start) and the geospatial
commuting city (geopandas, shapely and pyproj come from Pyodide).

What does not work in a browser tab: anything that starts threads or processes (parallel
`run_batch` and experiment executors, the threaded LLM client falls back to one call at a
time), network access other than `fetch` (a live LLM provider, OpenStreetMap downloads),
and packages Pyodide does not build. The page reports a package it cannot find in its
footer; the model then fails on the import with a normal traceback in the status line.

## First load

Most of a first visit is Pyodide itself and the two packages every model needs: the
WebAssembly interpreter (3.4 MB compressed), its standard library (2.5 MB), numpy (3.0 MB)
and pandas (4.2 MB), about 13.5 MB from the CDN. The site adds 0.5 MB (the pure wheel) or
0.85 MB (the compiled one). A model that uses scipy (the grid models' neighbour sums, the
continuous and network spaces' KD-trees) adds 14 MB more.

Measured with `tools/web/measure_load.py`: a cold first visit (fresh browser context, HTTP
cache off) in headless Chromium 1248 on Linux, the site served from localhost and Pyodide
from `cdn.jsdelivr.net`, the clock running from navigation to the model built and drawn at
step 0. The machine (16 cores) was shared with other jobs, which slows the WebAssembly
start-up; three runs per row (two for forest fire), median shown.

| Site | Transferred | No throttling | 50 Mbit/s, 40 ms | DevTools "Fast 4G" |
|---|---|---|---|---|
| Age-structured SEIR (zoo), pure wheel | 14.1 MB | 5.9 s | 8.0 s | 21.4 s |
| Age-structured SEIR (zoo), compiled wheel | 14.4 MB | | | 22.4 s |
| Forest fire (zoo, needs scipy), pure wheel | 28.0 MB | | 12.3 s | 36.8 s |

"Fast 4G" is Chrome DevTools' preset: 9 Mbit/s down at 90% efficiency (about 1 MB/s),
165 ms round trip. At that speed the transfer alone takes 14 s, so no export can start in
under 10 s there; on a 50 Mbit/s line a zoo model without scipy is ready in 8 s.

Later visits read Pyodide and the packages from the browser cache and start in a few
seconds. `tools/web/measure_load.py SITE_DIR --profile fast-4g` measures a site the same way.
