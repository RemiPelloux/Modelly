# Provenance

Manifests, verification, bundles and ODD skeletons behind `modelly run`, `modelly verify`, `modelly bundle` and `modelly odd`. How to use them to publish a study is in [Publishing a reproducible study](https://remipelloux.github.io/Modelly/dev/provenance.html).

Provenance and reproducible publication: manifests, verification, bundles and ODD.

`modelly run` runs a model once and writes its collected data and a manifest that records the code, environment, scenario, seeds, inputs, outputs and timing. `modelly verify` reruns a manifest and reports the first output that differs. `modelly bundle` packs a run into a deterministic zip for an archive such as Zenodo. `modelly odd` writes an ODD protocol skeleton from the model’s code.

The same steps from Python:

```default
from modelly.provenance import RunSpec, bundle, run_study, verify

run_study(RunSpec("model.py:Epidemic", out=Path("runs"), steps=100, seed=1))
assert verify(Path("runs/manifest.json")).matches
bundle(Path("runs"), Path("study.zip"))
```

The run manifest: a versioned JSON record of what produced a set of outputs.

`format` names the schema and its major version (`modelly-manifest/1`). A reader accepts any manifest of the same major version and refuses others, so fields can be added without breaking old readers. Paths are relative to the manifest’s folder and written with forward slashes; hashes are `sha256:<hex>` over bytes.

Top-level fields (all present in version 1):

```default
format       the schema name and version
target       {"kind": "file" | "module", "source", "class"}; a file source is
             relative to code.root
code         {"root", "files": {path: hash}, "hash", "git": {"commit", "dirty",
             "diff_hash"} | null}
environment  {"modelly": {"version", "build", "native"}, "python", "platform",
             "dependencies": {name: version}, "packages": {name: version}}
scenario     {"file", "hash", "parameters", "resolved"}
run          {"steps", "seed"}
seeds        {"seed", "entropy", "spawn_key", "stdlib_seed"}
inputs       [{"path", "hash"}]
outputs      [{"table", "path", "format", "hash", "rows", "columns"}]
timing       {"wall_seconds", "cpu_seconds"}
```

Optional fields (added within version 1, absent when they do not apply):

```default
llm_cache    {"path", "hash", "responses"}: the replies of the model's
             language-model clients, replayed by ``modelly verify``
```

#### `exception ManifestError`

A manifest that cannot be read, or one written in an unsupported format.

#### `json_safe(value: Any) → Any`

`value` if JSON can hold it, else its `repr` (documents, never re-reads).

#### `manifest_path(path: Path) → Path`

`path` itself, or the manifest inside it when `path` is a run folder.

#### `check_format(record: Any) → None`

Raise ManifestError unless `record` is a version-1 manifest with every field.

#### `read_manifest(path: Path) → dict[str, Any]`

The manifest at `path` (a file or a run folder), checked against the schema.

#### `write_manifest(folder: Path, record: dict[str, Any]) → Path`

Check and write `record` as `folder/manifest.json` atomically; its path.

Run a model once and record it: outputs on disk and a manifest next to them.

#### `class RunSpec(target: str, out: Path, steps: int, seed: int | None = None, scenario: Path | None = None, params: dict[str, ~typing.Any]=<factory>, inputs: tuple[~pathlib.Path, ...]=())`

What `modelly run` was asked to do.

#### `read_scenario(path: Path | None) → dict[str, Any]`

The parameters of a TOML scenario file (a flat table); `{}` for no file.

#### `run_study(spec: RunSpec) → dict[str, Any]`

Run the model `spec` names, write its outputs and manifest to `spec.out`.

Raises TargetError when the target, scenario or inputs cannot be used; anything the model raises propagates.

Rerun a recorded run from its manifest and compare the new outputs with the old.

The rerun uses the manifest’s target, parameters, seed and step count, writes its outputs to a temporary folder in the recorded formats, reads both sets back and reports the first table, column and row where they differ. A run whose model called a language model is rerun from the replies it recorded (`llm_cache`), offline. Changes that do not stop the rerun (code files, input files or the environment differ from the record) are notes.

#### `class Verification(difference: Difference | None, notes: list[str] = <factory>)`

The outcome of [`verify()`](https://remipelloux.github.io/Modelly/dev/apis/provenance.html#modelly.provenance.verify.verify): the first difference (None if all match) and notes.

#### `property matches: bool`

True when every recorded output was reproduced.

#### `verify(path: Path, tolerance: Tolerance | None = None) → Verification`

Rerun the manifest at `path` (a file or run folder) and compare outputs.

Raises ManifestError for an unreadable manifest and TargetError when the model cannot be loaded; anything the model raises propagates.

Find the first place where two runs’ output tables differ.

Numeric columns are compared with `numpy.isclose` under the given tolerances (both 0 by default: the values must be identical); other columns must be equal. Missing values match missing values.

#### `class Difference(table: str, message: str, column: str | None = None, row: int | None = None)`

Where an output differs: table, then column and row when the shapes agree.

#### `class Tolerance(rtol: float = 0.0, atol: float = 0.0)`

Relative and absolute tolerance for numeric columns.

#### `first_difference(table: str, expected: DataFrame, actual: DataFrame, tolerance: Tolerance = Tolerance(rtol=0.0, atol=0.0)) → Difference | None`

The first differing column, row and values of one table, or None if they match.

Columns are scanned in table order and rows top to bottom; the reported row is the row’s position (0-based) in the table.

Pack a recorded run into one deterministic zip a reviewer can verify.

The archive holds the manifest (its paths rewritten for the archive layout), the outputs, the language-model replies the run recorded (if any), the model’s source files under `code/`, the input files under `inputs/`, `requirements.lock`, `seeds.json`, Zenodo metadata (`.zenodo.json`) and a `CITATION.cff` stub. Entries are sorted, stored uncompressed and stamped with a fixed time and mode, so the same run gives the same bytes on every machine.

#### `exception BundleError`

The run folder does not hold what its manifest records.

#### `bundle_entries(folder: Path) → dict[str, bytes]`

Archive name to bytes for the run recorded in `folder`.

#### `bundle(folder: Path, out: Path) → Path`

Write the bundle of the run in `folder` (or of a manifest path) to `out`.

Raises ManifestError for an unreadable manifest and BundleError when outputs or code changed since the run.

The language-model replies of a recorded run, so a rerun needs no network.

`modelly run` exports the replies every [`modelly.llm.Client`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Client) of the model holds (its attributes, `model.llm` by convention) to `llm-responses.jsonl.gz` next to the outputs, and records it in the manifest as `llm_cache` (`{"path", "hash", "responses"}`). `modelly bundle` packs that file, and `modelly verify` reruns the model inside `modelly.llm.replay.replaying` so every client answers from it, read-only: the study verifies offline, and a call the record does not hold stops the rerun with `CacheMiss`. A run without a client records nothing and its manifest has no `llm_cache`.

#### `model_clients(model: Any) → list[Client]`

The distinct clients among the model’s attributes, in attribute order.

#### `cache_record(model: Any, out: Path) → dict[str, Any] | None`

Export the replies of the model’s clients to `out`; the manifest entry.

**Returns:**

`{"path", "hash", "responses"}`, or None when the model has no client.

#### `cache_problem(manifest: dict[str, Any], folder: Path) → str | None`

Why the recorded cache cannot be used as recorded, or None if it can.

#### `replay_for(manifest: dict[str, Any], folder: Path) → AbstractContextManager[object]`

Replay the run’s recorded replies, or nothing when there are none to replay.

An ODD protocol skeleton (Grimm et al.’s Overview, Design concepts, Details) for a model.

The seven ODD elements are written from what `modelly.provenance.odd_facts` finds in the code; every place only the modeller can fill holds a `TODO` marker.

#### `odd_markdown(model: Model[Any, Any]) → str`

The ODD skeleton of a built model, as Markdown.
