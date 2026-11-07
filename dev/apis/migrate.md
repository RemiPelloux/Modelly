# Migrate

The Mesa to Modelly codemod behind `python -m modelly.migrate`. The construct-by-construct map is in [Migrating from Mesa](https://remipelloux.github.io/Modelly/dev/migrating_from_mesa.html).

Codemod for moving a Mesa model to Modelly.

Run as `python -m modelly.migrate PATH [PATH ...] [--write]`. Without `--write` nothing is changed: the diff and the report are printed.

The rewrites are the mechanical part of `docs/migrating_from_mesa.md` (imports, agent constructors, a few model attributes). Everything that needs a decision (schedulers, legacy grids, batch runs, simulators) is left in place and reported with the guide section to read.

#### `class Finding(path: Path, line: int, text: str, reason: str, section: str)`

One line that needs a human decision.

#### `class FileResult(path: Path, original: str, migrated: str, findings: list[Finding])`

The outcome of migrating one file.

#### `property changed: bool`

Whether any rewrite applied.

#### `map_module(name: str) → str`

Translate a dotted `mesa...` module name to its Modelly module.

#### `rewrite_line(line: str) → str`

Apply the import and expression rewrites to one line.

#### `find_flags(path: Path, lines: list[str]) → list[Finding]`

Collect the lines that still need a decision after rewriting.

#### `migrate_source(path: Path, source: str) → FileResult`

Rewrite one file’s source and report what is left to do.

#### `python_files(paths: list[Path]) → list[Path]`

Expand files and directories into the Python files to migrate.

#### `render_diff(result: FileResult) → str`

Unified diff of the rewrites for one file.

#### `render_report(results: list[FileResult]) → str`

The human-facing report: rewrites applied and decisions left.

#### `migrate(paths: list[Path], write: bool = False) → list[FileResult]`

Migrate the Python files under `paths`; write them back if `write`.

#### `build_parser(prog: str = 'python -m modelly.migrate') → ArgumentParser`

The argument parser, with examples and exit codes in its help.

#### `main(argv: list[str] | None = None, prog: str = 'python -m modelly.migrate') → int`

Command-line entry point; `prog` names the command in –help.

## Checking a project for 2.0

`modelly migrate --check-2.0`: what a project must change before Modelly 2.0.

Every deprecation of the 2.0 inventory (`modelly/_inventory.py`) that code can show is looked for in the project’s Python files, by reading them (nothing is imported or run):

- calls of the renamed visualisation helpers, and the `SpaceRenderer` calls that pass arguments to `render`, `draw_agents`, `draw_structure` or `draw_property_layer`;
- an `agent_portrayal` that returns a dict, a `property_layer_portrayal` given as a dict;
- the synthetic-population names imported from `modelly.space.geo`;
- a `Scenario` subclass attribute without an annotation.

Each is a **change**, with the line and what to write instead. The 2.0 changes no warning can show are **notes**: a `Model` subclass without `agent_streams = True` draws other numbers in 2.0 (per-agent streams by default, epic H6), and a `requires-python` below 3.13 must be raised (H9). The exit status is 1 when there is a change to make, so the check fits a test or a pre-commit hook.

#### `class Finding(kind: str, path: Path, line: int, message: str)`

One thing to change, or to know, before 2.0.

#### `check_file(path: Path) → list[Finding]`

Every finding of one Python file; a file that does not parse is reported as a note.

#### `python_files(paths: Iterable[Path]) → list[Path]`

The `.py` files of `paths` (files and folders), sorted.

#### `check(paths: Iterable[Path]) → list[Finding]`

The findings of every Python file under `paths`, and of their projects’ metadata.

#### `report(findings: list[Finding]) → str`

The findings, changes first, then a summary line.
