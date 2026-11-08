# Plugins

`modelly.plugins` finds third-party extensions through package entry points. The guide is [Plugins](https://remipelloux.github.io/Modelly/dev/plugins.html).

Third-party extensions found through package entry points.

A package extends Modelly by declaring entry points in one of the groups of `GROUPS`, for example in its `pyproject.toml`:

```default
[project.entry-points."modelly.spaces"]
hexworld = "hexworld.space:HexWorld"
```

`discover(group)` lists what is installed without importing anything; each `Plugin` is imported the first time it is loaded.

**Plugin API v1.** The groups, `Plugin`, `discover` and `load_all` are frozen for the 1.x line (`API_VERSION`). A plugin declares the Modelly versions it supports as an ordinary dependency, `"modelly-abm>=1.5,<2"`; `Plugin.compatible` checks it against the running Modelly (a pre-release or development build counts as its release), and loading a plugin whose declaration excludes it raises `PluginError` instead of importing code written for another version. A plugin that fails to import raises `PluginError` naming the plugin and its distribution, and never stops the others from being found or loaded: `load_all` returns the loaded objects and the errors apart.

from modelly.plugins import discover

spaces = discover(“modelly.spaces”) # {“hexworld”: Plugin(…)} HexWorld = spaces[“hexworld”].load()

#### `exception PluginError`

A plugin could not be loaded; `__cause__` is the original error.

#### `class Plugin(name: str, group: str, value: str, distribution: str | None, requires: str | None, _entry_point: EntryPoint, _loaded: Any = <object object>)`

One entry point: imported on the first `load` and cached.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the entry point’s name, the key in `discover`’s result.
- **group** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – its group, such as `"modelly.spaces"`.
- **value** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the `module:attribute` it points to.
- **distribution** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – the installed distribution that declares it, if known.
- **requires** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – the distribution’s version specifier on `modelly-abm` (`">=1.5,<2"`), `""` for any version, None when it does not declare Modelly at all.

#### `load() → Any`

Import and return the object the entry point names.

**Raises:**

[**PluginError**](https://remipelloux.github.io/Modelly/dev/apis/plugins.html#modelly.plugins.PluginError) – if importing or resolving it fails, with the original error as its cause.

#### `property compatible: bool`

Whether the running Modelly meets the plugin’s declaration (true without one).

#### `clear_cache() → None`

Forget the scanned entry points: the next `discover` reads them again.

#### `discover(group: str) → dict[str, Plugin]`

The installed plugins of `group`, by name, sorted; nothing is imported.

Any group name works, so a feature may define its own; `GROUPS` lists Modelly’s. When two distributions declare the same name, the first distribution in alphabetical order wins and a `RuntimeWarning` names both.

Example

```default
>>> discover("modelly.no_such_group")
{}
```

#### `load_all(group: str) → tuple[dict[str, Any], dict[str, PluginError]]`

Load every plugin of `group`: `(objects by name, errors by name)`.

A plugin that fails is reported in the second dictionary; the others still load.

## The model builder

The model builder: a few choices in a form, one ordinary Modelly `model.py` out.

For teaching. A `ModelSpec` names one kind of agent, how many there are, the size of the grid they live on, and their behaviours, picked from `BEHAVIOURS` (walk to a random neighbouring cell, give wealth to a cellmate, catch an infection from cellmates, recover). `build_code(spec)` writes a single module with a `Scenario` holding every parameter, the agent class with its `Column` attributes and one method per behaviour, and the model with its grid and a `DataCollector`: code a student reads, runs and changes, which passes `modelly lint`. Studio’s Builder tab is a form over it.

#### `class Behaviour(summary: str, columns: tuple[tuple[str, str, str], ...], parameters: tuple[tuple[str, str, str], ...], body: tuple[str, ...], reporters: tuple[tuple[str, str], ...] = ())`

One behaviour: its columns, its parameters, its method body and its reporters.

#### `exception BuilderError`

A spec the builder cannot write a model from; the message says why.

#### `class ModelSpec(name: str = 'Classroom', agent: str = 'Student', count: int = 100, width: int = 20, height: int = 20, behaviours: tuple[str, ...]=('walk', ), initially_infected: int = 5, seed: int = 42, steps: int = 100, extra: dict[str, str]=<factory>)`

What the form chose.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the model class’s name (CapWords); the agent is `agent`.
- **agent** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the agent class’s name (CapWords).
- **count** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – how many agents.
- **width** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the grid’s width, in cells.
- **height** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the grid’s height, in cells.
- **behaviours** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – names of `BEHAVIOURS`, in the order the agent does them each step.
- **initially_infected** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – agents infected at the start (with `infect`).

#### `check() → None`

Refuse names that are not class names, unknown behaviours, bad sizes.

#### `build_code(spec: ModelSpec) → str`

The `model.py` the spec describes.

**Raises:**

[**BuilderError**](https://remipelloux.github.io/Modelly/dev/apis/plugins.html#modelly.new.builder.BuilderError) – for a spec `ModelSpec.check` refuses.
