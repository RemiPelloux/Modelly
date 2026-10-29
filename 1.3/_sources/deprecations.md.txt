# Deprecations

Modelly changes its public API only in a way you can see coming. This page is the policy, the
list of what is deprecated now, and how to find and silence the warnings.

## The policy

1. **Nothing is removed without a warning first.** A deprecated name keeps working and raises a
   warning for at least one minor release before it can go.
2. **The warning tells you what to do.** Every message names the replacement and the release
   that removes the old name:

   ```text
   make_space_altair() is deprecated and will be removed in Modelly 2.0; use make_altair_space() instead.
   ```

3. **Removals happen only in a major release.** Everything deprecated during 1.x is removed in
   2.0, not before. Minor releases add and deprecate; they never remove.
4. **One mechanism.** Every deprecation goes through `modelly._deprecation.deprecated(name,
   replacement, removal="2.0")`, which refuses to warn without a replacement or with a removal
   before 2.0. A test fails if any module in `modelly/` raises a deprecation warning itself.

The warning class is `ModellyDeprecationWarning`. It is a `DeprecationWarning`, so the
standard Python tools find it, and also a `FutureWarning`, so filters written for the warnings
Modelly 1.2 raised keep matching.

## Finding them in your code

Python shows a `DeprecationWarning` when the deprecated call is in the script you run, in a
notebook, or under pytest. To find every one, including those raised from your own modules,
turn them into errors and run your model or its tests:

```bash
python -W error::DeprecationWarning my_model.py
python -W error::DeprecationWarning -m pytest
```

In PowerShell the commands are the same. To see them without stopping at the first:

```bash
python -W always::DeprecationWarning my_model.py
```

## Silencing them

Fix the call: the message says what to write instead. When you cannot change the code yet,
silence Modelly's deprecations only, so that warnings from other libraries still show:

```python
import warnings
from modelly._deprecation import ModellyDeprecationWarning

warnings.filterwarnings("ignore", category=ModellyDeprecationWarning)
```

In a pytest configuration (`pyproject.toml`):

```toml
[tool.pytest.ini_options]
filterwarnings = ["ignore::modelly._deprecation.ModellyDeprecationWarning"]
```

## Deprecated now

| Deprecated | Use instead | Removed in |
|---|---|---|
| `make_space_altair()` | `make_altair_space()` | 2.0 |
| `make_space_matplotlib()` | `make_mpl_space_component()` | 2.0 |
| `make_plot_measure()` | `make_mpl_plot_component()` | 2.0 |
| returning a dict from `agent_portrayal` | an `AgentPortrayalStyle` | 2.0 |
| a `property_layer_portrayal` dict | a callable returning a `PropertyLayerStyle` | 2.0 |
| `SpaceRenderer.render(...)` with arguments | `setup_structure()`, `setup_agents()` and `setup_property_layer()`, then `render()` | 2.0 |
| `draw_agents(agent_portrayal, **kwargs)` | `setup_agents(agent_portrayal, **kwargs)`, then `draw_agents()` | 2.0 |
| `draw_structure(**kwargs)` | `setup_structure(**kwargs)`, then `draw_structure()` | 2.0 |
| `draw_property_layer(property_layer_portrayal)` | `setup_property_layer(...)`, then `draw_property_layer()` | 2.0 |

## Deprecating something (for contributors)

```python
from modelly._deprecation import deprecated


def old_name(*args, **kwargs):
    deprecated("old_name()", "new_name()")
    return new_name(*args, **kwargs)
```

`stacklevel` counts from the caller of `deprecated`, like `warnings.warn` counts from its
caller: the default (2) points the warning at whoever called `old_name`. Add the row to the
table above and a changelog entry under "Deprecated" in the same change.

The stability level of every public name (stable or provisional) is in
[`docs/api_stability.toml`](https://github.com/RemiPelloux/Modelly/blob/main/docs/api_stability.toml):
a stable name follows this policy; a provisional one (new in 1.3) may still change in a minor
release, with a changelog entry.
