# Plugins

A separate package can add spaces, executors, samplers, collectors, Studio views and lint
rules to Modelly without any change to Modelly itself. It declares them as
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/) in its
`pyproject.toml`, and Modelly finds them once the package is installed.

## Entry-point groups

| Group | What the entry point names |
|---|---|
| `modelly.spaces` | a space class (a grid, a mesh, a geographic space) |
| `modelly.executors` | an executor that runs batches of model runs (processes, a cluster) |
| `modelly.samplers` | a sampler of parameter designs (Sobol, Latin hypercube, Halton) |
| `modelly.collectors` | a data collector or a reporter factory |
| `modelly.studio_views` | a view for Modelly Studio |
| `modelly.lint_rules` | a rule for `modelly lint` |

The groups are listed in `modelly.plugins.GROUPS`. What each kind of object must provide is
set by the feature that uses it; the discovery mechanism below is the same for all.

## What Modelly does with each group

| Group | Read by | The entry point names |
|---|---|---|
| `modelly.executors` | `Experiment.run(executor=name)`, `modelly experiment` | an `Executor` subclass (or a factory taking the executor's options) |
| `modelly.samplers` | `[design] kind = "name"` in an experiment file; `modelly.experiments.designs.design_factory(name)` | a factory `n -> Design`, as `designs.latin_hypercube` |
| `modelly.lint_rules` | `modelly lint` (and the Studio lint panel) | an object with `rule`, a `modelly.lint.Rule` with a code of its own, and `check(tree)`, yielding the `(line, column)` of each hit in the parsed module |
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
(`print()` in model code) and a Studio tab showing the scenario. `pip install -e` it next to
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
  is used.
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
