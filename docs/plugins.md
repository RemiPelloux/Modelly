# Plugins

A separate package can add spaces, executors, samplers, collectors, Studio views and lint
rules to Modelly without any change to Modelly itself. It declares them as
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/) in its
`pyproject.toml`, and Modelly finds them once the package is installed.

```bash
modelly new hexworld --template plugin   # a plugin package, tested, for Modelly 1.x
modelly plugins --check                  # what is installed, for which Modelly, and does it load
```

## Plugin API v1

The entry-point groups below, `Plugin`, `discover`, `load_all` and `PluginError` are the
plugin API, version 1 (`modelly.plugins.API_VERSION`). They are **stable and frozen for the
1.x line**: no group is renamed or removed and the loading rules below do not change before
2.0, which carries them over unchanged or with a migration path. A plugin written for 1.5 keeps
working in every later 1.x release.

## Entry-point groups

| Group | What the entry point names |
|---|---|
| `modelly.spaces` | a space class (a grid, a mesh, a geographic space) |
| `modelly.executors` | an executor that runs batches of model runs (processes, a cluster) |
| `modelly.samplers` | a sampler of parameter designs (Sobol, Latin hypercube, Halton) |
| `modelly.collectors` | a data collector or a reporter factory |
| `modelly.studio_views` | a view for Modelly Studio |
| `modelly.lint_rules` | a rule for `modelly lint` |
| `modelly.hub_sources` | an extra hub index: a URL or path, or a function returning one or several |

The groups are listed in `modelly.plugins.GROUPS`. What each kind of object must provide is
set by the feature that uses it; the discovery mechanism below is the same for all.

## What Modelly does with each group

| Group | Read by | The entry point names |
|---|---|---|
| `modelly.executors` | `Experiment.run(executor=name)`, `modelly experiment` | an `Executor` subclass (or a factory taking the executor's options) |
| `modelly.samplers` | `[design] kind = "name"` in an experiment file; `modelly.experiments.designs.design_factory(name)` | a factory `n -> Design`, as `designs.latin_hypercube` |
| `modelly.lint_rules` | `modelly lint` (and the Studio lint panel) | an object with `rule`, a `modelly.lint.Rule` with a code of its own, and `check(tree)`, yielding the `(line, column)` of each hit in the parsed module |
| `modelly.hub_sources` | `modelly hub search`, `info` and `install`, after the public index | a URL or path string, or a function returning one or a list |
| `modelly.studio_views` | `modelly studio`: one more tab, named after the entry point | a Solara component taking the Studio state, as the built-in views |
| `modelly.spaces` | your model, through `discover("modelly.spaces")[name].load()` | a space class |
| `modelly.collectors` | your model, through `discover("modelly.collectors")[name].load()` | a reporter or a reporter factory for `DataCollector` |

No Modelly feature picks a space or a collector by name (a model constructs its space and its
reporters itself), so those two groups are read by models, not by Modelly. A lint rule that
reuses a built-in code, or a view or rule that fails to load, is skipped with a
`RuntimeWarning`; the others still run.

## An example plugin

[`examples/plugins/modelly-example-plugin`](https://github.com/RemiPelloux/Modelly/tree/main/examples/plugins/modelly-example-plugin)
is a complete third-party package with one entry point in every group: a ring of cells, a
uniform random sampler, a share-of-agents reporter, an executor, the lint rule `EXP001`
(`print()` in model code), a Studio tab showing the scenario and a hub source (an empty
private index). `pip install -e` it next to
Modelly to try it; `tests/test_example_plugin.py` checks each entry point the way Modelly reads
it.

## Declaring a plugin

```toml
# pyproject.toml of the package "modelly-hexworld"
[project.entry-points."modelly.spaces"]
hexworld = "hexworld.space:HexWorld"

[project.entry-points."modelly.samplers"]
halton = "hexworld.sampling:halton"
```

After `pip install modelly-hexworld` (or `pip install -e .` while you develop it) the
entry points are visible to every Python process using that environment.

### Which Modelly a plugin supports

A plugin declares the Modelly versions it works with as an ordinary dependency, with a lower
bound on the minor version it was written for and an upper bound below the next major:

```toml
[project]
dependencies = ["modelly-abm>=1.5,<2"]
```

Modelly reads that requirement from the installed metadata (`Plugin.requires`, here
`">=1.5,<2"`). When the running version is outside it, `Plugin.compatible` is false and
`load()` raises `PluginError` without importing the plugin's code, so a plugin built for
another version is skipped with a warning by the feature that reads it instead of failing
inside it. A plugin that does not mention `modelly-abm` loads as before (`requires` is None);
`modelly plugins` marks it as declaring no version.

### Starting from the template

`modelly new hexworld --template plugin` writes a package with one entry point (a stratified
design sampler under `modelly.samplers`), the declaration above for the running minor version,
and tests that check the entry point and that the same seed gives the same points. Replace the
sampler with your extension, or add modules and entry points next to it.

### Checking what is installed

```text
$ modelly plugins --check
Modelly 1.5.0, plugin API v1
modelly.spaces: 1
  ring            modelly-example-plugin      modelly-abm>=1.4,<2     ok
modelly.executors: 1
  in_order        modelly-example-plugin      modelly-abm>=1.4,<2     ok
...
```

Without `--check` nothing is imported; with it every plugin is loaded, and the command exits
with 1 when one is incompatible or fails to import.

## Finding and loading plugins

```python
from modelly.plugins import discover, load_all

spaces = discover("modelly.spaces")  # {"hexworld": Plugin(...)}; nothing imported yet
HexWorld = spaces["hexworld"].load()  # imported now, then cached

loaded, errors = load_all("modelly.samplers")  # every plugin of the group
for name, error in errors.items():
    print(f"{name} did not load: {error}")
```

- **Lazy.** `discover(group)` reads the installed metadata only; a plugin's module is imported
  the first time `load()` is called on it, so a slow or heavy plugin costs nothing until it
  is used. The scan of the installed metadata is kept for the session and redone when
  `sys.path` or one of its folders changes; `modelly.plugins.clear_cache()` forces it, for
  example after installing a plugin into a running process.
- **Isolated.** A plugin that fails to import raises `PluginError` (an `ImportError`) that
  names the plugin, its entry point and its distribution, with the original error as its
  cause. It never stops other plugins from being found or loaded; `load_all` returns the
  failures apart from the objects.
- **Deterministic.** Plugins come back sorted by name. When two installed distributions
  declare the same name in a group, the first distribution in alphabetical order wins and a
  `RuntimeWarning` names both.

Any group name works with `discover`, so a feature can define its own group with the same
helper.

## Testing a plugin

A test does not need to build or install a package: a folder on `sys.path` that holds a
`<name>-<version>.dist-info` directory with a `METADATA` file and an `entry_points.txt` is an
installed distribution as far as `importlib.metadata` is concerned. `tests/test_plugins.py`
does exactly that with pytest's `tmp_path` and `monkeypatch.syspath_prepend`.

```text
fake-site/
  fakeplug-1.0.dist-info/
    METADATA            Metadata-Version: 2.1 / Name: fakeplug / Version: 1.0
    entry_points.txt    [modelly.spaces]
                        ring = fake_modelly_plugin:Ring
  fake_modelly_plugin.py
```

The API is on the [plugins API page](apis/plugins.md).
