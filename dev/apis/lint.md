# Lint

The static checks behind `python -m modelly.lint`. The rules, with examples, are in [Lint](https://remipelloux.github.io/Modelly/dev/lint.html).

Static checks for Modelly models: bugs that break reproducibility and loops that scale badly.

Run as `python -m modelly.lint PATH [PATH ...]`. Nothing is imported or executed: the source is parsed and walked. A finding on a line ending in `# noqa` (or `# noqa: MDL101`) is skipped, and `[tool.modelly.lint]` in pyproject.toml selects and ignores rules (see `modelly.lint.config`). The rules, with examples, are in `docs/lint.md`; `--explain CODE` prints one of them.

#### `class Finding(path: str, line: int, column: int, rule: Rule)`

One rule hit at a place in a file.

#### `location() → str`

`path:line:col: CODE message`, the format editors jump to.

#### `class Rule(code: str, severity: str, message: str, hint: str)`

One check: its code, how serious it is, what it found and what to do instead.

#### `lint_paths(paths: Iterable[str | Path]) → list[Finding]`

Return the findings for every Python file in `paths`.

**Raises:**

[**SyntaxError**](https://docs.python.org/3/builtins/exceptions.html#SyntaxError) – when a file is not valid Python.

#### `lint_source(source: str, path: str = '<string>', siblings: SiblingColumns | None = None) → list[Finding]`

Return the findings for one module’s source, sorted by position.

`siblings` resolves the agent classes the module imports from other files of the project, so MDL107 knows their Column attributes; without it only this source counts.

**Raises:**

[**SyntaxError**](https://docs.python.org/3/builtins/exceptions.html#SyntaxError) – when `source` is not valid Python.

The rules of `modelly.lint` and the AST helpers they share.

Codes below 100 are errors: the model runs but gives a wrong or unreproducible result. Codes from 100 are warnings: the model is right but its cost grows faster than it needs to.

#### `class Rule(code: str, severity: str, message: str, hint: str)`

One check: its code, how serious it is, what it found and what to do instead.

#### `dotted(node: AST | None) → list[str]`

Return the names along an attribute chain: `self.model.agents` -> self, model, agents.

#### `is_population(node: AST | None, in_model: bool) → bool`

Whether `node` is the model’s whole population or one type of it, not a cell’s agents.

#### `is_set_expr(node: AST) → bool`

Whether `node` builds a set, whose iteration order follows memory addresses.

#### `is_mutable_literal(node: AST | None) → bool`

Whether `node` is `[]`, `{}`, a set literal or an empty list/dict/set call.

#### `calls_super_init(func: FunctionDef | AsyncFunctionDef) → bool`

Whether `func` calls `super().__init__` or `<Base>.__init__(self, ...)`.

#### `branches(func: FunctionDef | AsyncFunctionDef) → int`

Count the decision points of `func`: its cyclomatic complexity minus one.

Lint rules from other packages: the `modelly.lint_rules` entry-point group.

An entry point names an object with two attributes: `rule`, a `Rule` whose code is not one of Modelly’s, and `check(tree)`, which takes the parsed module (`ast.Module`) and yields the `(line, column)` of every hit. `# noqa` and the `[tool.modelly.lint]` selection apply to plugin codes as to built-in ones.

A plugin that fails to load, lacks either attribute or reuses a built-in code is left out with a `RuntimeWarning` naming it; the other rules still run. Plugins are read once per process (`plugin_rules.cache_clear()` reads them again).

#### `plugin_rules() → dict[str, Any]`

The usable plugin rules, by code.

#### `all_rules() → dict[str, Rule]`

The built-in rules, then the plugin rules, by code.

#### `plugin_hits(tree: Module) → set[tuple[int, int, str]]`

`(line, column, code)` of every plugin rule’s hit in `tree`.

The `[tool.modelly.lint]` table of pyproject.toml: which findings to keep.

``toml [tool.modelly.lint] select = ["MDL0", "MDL101"]           # only these codes or prefixes (default: all) ignore = ["MDL105"]                   # drop these codes or prefixes per-file-ignores = { "tests/*" = ["MDL001"], "setup_*.py" = ["MDL1"] } ``

The file is the first `pyproject.toml` found from the working directory upwards; per-file patterns are globs on the path relative to that file’s folder, or on the bare file name. `--select` and `--ignore` on the command line replace the file’s values.

#### `exception ConfigError`

The `[tool.modelly.lint]` table has a key or value the linter does not know.

#### `prefixes(value: str | list[str]) → tuple[str, ...]`

Normalise `"MDL0, MDL101"` or `["MDL0", "MDL101"]` to upper-case prefixes.

#### `matches(code: str, codes: tuple[str, ...]) → bool`

Whether `code` starts with one of `codes`.

#### `class Config(select: tuple[str, ...] = (), ignore: tuple[str, ...] = (), per_file_ignores: tuple[tuple[str, tuple[str, ...]], ...] = (), root: Path = PosixPath('.'))`

Which findings to keep: the select, ignore and per-file-ignores settings.

#### `keeps(finding: lint.Finding) → bool`

Whether `finding` survives select, ignore and its file’s ignores.

#### `file_ignores(path: str) → tuple[str, ...]`

The codes ignored for `path` by the per-file-ignores patterns it matches.

#### `find_pyproject(start: Path) → Path | None`

The first `pyproject.toml` in `start` or one of its parents.

#### `load_config(start: Path | None = None) → Config`

Read `[tool.modelly.lint]` from the nearest pyproject.toml; empty when there is none.

**Raises:**

- [**ConfigError**](https://remipelloux.github.io/Modelly/dev/apis/lint.html#modelly.lint.config.ConfigError) – on an unknown key or a value that is not a list of codes.
- [**tomllib.TOMLDecodeError**](https://docs.python.org/3/library/tomllib.html#tomllib.TOMLDecodeError) – when the file is not valid TOML.
