# Publishing a reproducible study

Four commands take a model from one run on your machine to an archive a reviewer can rerun
with a single command. `modelly run` writes the outputs and a manifest that records everything
that produced them; `modelly verify` reruns a manifest and compares; `modelly bundle` packs a
run into one zip; `modelly odd` writes the skeleton of the model's ODD protocol description.
All four work the same on Windows, macOS and Linux, need no network, and use `git` only when
it is installed.

```bash
modelly run model.py:Epidemic --scenario scenario.toml --steps 365 --out runs/
modelly verify runs/manifest.json          # outputs match
modelly bundle runs/ --out epidemic-study.zip
modelly odd model.py:Epidemic > ODD.md
```

## For authors

### Run and record

```bash
modelly run model.py:Epidemic --scenario scenario.toml --steps 365 --out runs/
```

The target is a file and a class (`path/to/model.py:Epidemic`) or a dotted module
(`package.module:Epidemic`), as for [the profiler](profile.md). The scenario file is a flat
TOML table; a `seed` key is the seed, every other key is a parameter. Parameters the model's
constructor takes by name go to it, the others to its `Scenario`.

```toml
seed = 42
beta = 0.3
gamma = 0.1
```

`--param key=value` adds or overrides a parameter, `--seed` overrides the seed, and
`--input data.csv` (repeatable) records the hash of a data file the model reads. Without any
seed a seed is drawn and recorded, so even that run can be repeated.

The run folder then holds one file per table the model's `DataCollector` holds and
`manifest.json`:

| File | Content |
|---|---|
| `model.parquet` | model reporters, one row per collection |
| `agents.parquet` | agent reporters, with `Step` and `AgentID` |
| `agents_<Class>.parquet` | agent-type reporters |
| `table_<name>.parquet` | each `DataCollector` table |
| `manifest.json` | the record described below |

Parquet needs `pyarrow`; without it, and for a table Parquet cannot hold (mixed objects), the
file is UTF-8 CSV. The manifest says which.

### What the manifest records

The manifest is JSON with a `format` field, `modelly-manifest/1`. A reader accepts any
manifest of its major version and refuses others with a clear error. Every path in it is
relative to the manifest's folder and written with forward slashes; every hash is
`sha256:<hex>` over the file's bytes.

| Field | Content |
|---|---|
| `target` | the model class and where it was loaded from (`file` or `module`) |
| `code` | the code root (the model file's folder), a hash of each model source file the run imported, one hash over all of them, and, inside a git working tree, the commit, whether the tree is dirty and a hash of the uncommitted diff |
| `environment` | Modelly's version and build (`compiled`, `pure` or `partial`, with the state of each compiled core), Python version and implementation, platform, the installed versions of Modelly's dependencies, and every installed package (`packages`) |
| `scenario` | the scenario file and its hash, the parameters given, and every value the model's scenario held |
| `run`, `seeds` | the step count, the seed and the seed sequence it expanded to |
| `inputs` | each `--input` file and its hash |
| `outputs` | each table: file, format, hash, rows and columns |
| `timing` | wall-clock and CPU seconds of building and running the model |

Cite the manifest, or its hash, next to every number in the paper it produced.

### Bundle for an archive

```bash
modelly bundle runs/ --out epidemic-study.zip
```

| Entry | Content |
|---|---|
| `manifest.json` | the manifest, its paths rewritten for the archive |
| outputs | the recorded tables |
| `llm-responses.jsonl.gz` | the language-model replies of the run, when its model has a `modelly.llm.Client` |
| `code/` | the model's source files |
| `inputs/` | the `--input` files and the scenario file |
| `requirements.lock` | `name==version` of every package installed at run time (`pip install -r`) |
| `seeds.json` | the seed, its seed sequence and the step count |
| `.zenodo.json` | Zenodo deposit metadata |
| `CITATION.cff` | a citation stub for the study that cites Modelly |

Entries are sorted, stored uncompressed and carry a fixed date and mode, so the same run gives
a byte-identical archive on any machine: the archive's hash identifies the study. Bundling
refuses a run whose outputs, code or recorded replies changed since `modelly run`.

A model that calls a language model through `modelly.llm` (a `Client` among its attributes,
`self.llm` by convention) gets its replies recorded: `modelly run` exports every reply its
clients hold to `llm-responses.jsonl.gz`, sorted by key, and the manifest names the file, its
hash and the number of replies (`llm_cache`). The bundle packs the file, and `modelly verify`
reruns the model with every client answering from it, read-only, whatever provider and cache
the model builds: the study verifies with no network and no API key, and a call the record does
not hold stops the rerun with `CacheMiss` instead of reaching the provider.

`.zenodo.json` and `CITATION.cff` hold `TODO` where only you know the answer: the title, the
creators, the licence. Fill them in, then upload the zip to [Zenodo](https://zenodo.org/),
which reads `.zenodo.json` and gives the deposit a DOI.

### Describe the model: ODD

```bash
modelly odd model.py:Epidemic > ODD.md
```

The [ODD protocol](https://doi.org/10.18564/jasss.4259) (Overview, Design concepts, Details)
is the usual way to describe an agent-based model in a paper. `modelly odd` builds the model
without running it and writes the seven elements, filled from the code where the code can say:

| Element | Filled from |
|---|---|
| 1. Purpose and patterns | the model class's docstring |
| 2. Entities, state variables and scales | each agent class, its `Column` declarations (`Agent.column_specs()`), its attributes and initial count; the model's scalar attributes; its spaces and their dimensions |
| 3. Process overview and scheduling | the statements of `step()` in order, and the agent methods it calls through `do`, `shuffle_do` or `map` |
| 4. Design concepts | the eleven concepts; Observation lists the `DataCollector` reporters |
| 5. Initialization | the scenario's parameters, defaults and values, and the initial population |
| 6. Input data | left to you |
| 7. Submodels | each agent method, scheduled ones first, with its docstring |

Every place that needs a human holds a `TODO` marker. `--scenario`, `--param` and `--seed`
build the model as `modelly run` does.

## For reviewers

Unpack the archive, install the lock file in a fresh environment, and verify:

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.lock
.venv/bin/modelly verify manifest.json
```

On Windows the scripts are in `.venv\Scripts\` instead of `.venv/bin/`.

`modelly verify` reruns the model with the recorded parameters, seed and step count, then
compares every output table with the recorded one, column by column and row by row. It prints
`outputs match`, or the first difference:

```text
outputs differ: table 'model', column 'Gini', row 12: expected 0.4312, got 0.4415
```

The row is the 0-based position in the table. Before the rerun it checks the code files, the
input files and the Modelly and Python versions against the record and prints what differs as
notes on stderr; a note alone does not fail the check.

Numeric columns are compared with `numpy.isclose`; both tolerances are 0 by default, so the
values must be identical. A study run on another processor or operating system may differ in
the last bits of some floating-point results; `--rtol 1e-12` (or `--atol`) accepts that, and a
report should say which tolerance it used.

| Exit code | `modelly verify` |
|---|---|
| 0 | outputs match |
| 1 | an output differs (the first difference is printed) |
| 2 | bad command line, unreadable or unsupported manifest, or the model cannot be loaded |
| 3 | the model raised during the rerun (traceback on stderr) |

`modelly run` and `modelly odd` exit 0 on success, 2 for a target or scenario that cannot be
used and 3 when the model raises; `modelly bundle` exits 0 or 2.

## For journals

A submission that ships the bundle lets the editor check three things without reading code:

- the archive's hash matches the one cited in the paper (the bundle is byte-deterministic);
- `modelly verify manifest.json` prints `outputs match` in a fresh environment built from
  `requirements.lock`;
- `ODD.md` and `CITATION.cff` are complete (no `TODO` left).

Rerunning needs neither the authors' machine nor a network connection.

## Limits

- The code root is the folder of the model file. Source files outside it that the model
  imports (an installed package) are identified by `environment.packages`, not by hash.
- Hashes are over bytes: a checkout that converts line endings (git's `autocrlf` on Windows)
  changes the hash of the source files, and `verify` notes it. The outputs are compared by
  value, so the check itself still passes.
- Parameters given as Python tuples are stored as JSON lists.
- A model that reads data files is rerun with the paths in its parameters; keep those paths
  relative to where the study is run, and record the files with `--input`.

From Python, the same steps are `modelly.provenance.run_study`, `verify`, `bundle` and
`odd_markdown` ([API](apis/provenance.md)).
