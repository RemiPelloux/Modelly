# Deprecations

Modelly changes its public API only in a way you can see coming. This page is the policy, the list of what is deprecated now, and how to find and silence the warnings.

## The policy

1. **Nothing is removed without a warning first.** A deprecated name keeps working and raises a warning for at least one minor release before it can go.
1. **The warning tells you what to do.** Every message names the replacement and the release that removes the old name:

```text
make_space_altair() is deprecated and will be removed in Modelly 2.0; use make_altair_space() instead.
```

1. **Removals happen only in a major release.** Everything deprecated during 1.x is removed in 2.0, not before. Minor releases add and deprecate; they never remove.
1. **One mechanism.** Every deprecation goes through `modelly._deprecation.deprecated(name, replacement, removal="2.0")`, which refuses to warn without a replacement or with a removal before 2.0. A test fails if any module in `modelly/` raises a deprecation warning itself.

The warning class is `ModellyDeprecationWarning`. It is a `DeprecationWarning`, so the standard Python tools find it, and also a `FutureWarning`, so filters written for the warnings Modelly 1.2 raised keep matching.

## Finding them in your code

Python shows a `DeprecationWarning` when the deprecated call is in the script you run, in a notebook, or under pytest. To find every one, including those raised from your own modules, turn them into errors and run your model or its tests:

```bash
python -W error::DeprecationWarning my_model.py
python -W error::DeprecationWarning -m pytest
```

In PowerShell the commands are the same. To see them without stopping at the first:

```bash
python -W always::DeprecationWarning my_model.py
```

## Silencing them

Fix the call: the message says what to write instead. When you cannot change the code yet, silence Modelly’s deprecations only, so that warnings from other libraries still show:

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

Deprecated

Use instead

Removed in

make_space_altair()

make_altair_space()

2.0

make_space_matplotlib()

make_mpl_space_component()

2.0

make_plot_measure()

make_mpl_plot_component()

2.0

returning a dict from agent_portrayal

an AgentPortrayalStyle

2.0

a property_layer_portrayal dict

a callable returning a PropertyLayerStyle

2.0

SpaceRenderer.render(...) with arguments

setup_structure(), setup_agents() and setup_property_layer(), then render()

2.0

draw_agents(agent_portrayal, **kwargs)

setup_agents(agent_portrayal, **kwargs), then draw_agents()

2.0

draw_structure(**kwargs)

setup_structure(**kwargs), then draw_structure()

2.0

draw_property_layer(property_layer_portrayal)

setup_property_layer(...), then draw_property_layer()

2.0

modelly.space.geo.ipf, modelly.space.geo.synthesize_population (and the same names in modelly.space.geo.population)

modelly.population.ipf, modelly.population.synthesize_population

2.0

modelly.space.geo.population.MAX_ITERATIONS, REGION, TOLERANCE

the same names in modelly.population.fitting

2.0

a Scenario subclass attribute without an annotation

an annotated field (beta: float = 0.3)

2.0

a parameter a Scenario subclass does not declare, or of another type than its annotation

an annotated field, and a value of its type

2.0

## Announced for 2.0

2.0 is the one release allowed to break things ([its roadmap](https://remipelloux.github.io/Modelly/dev/roadmap/2.0.0.html)). Everything it removes warns in a 1.x release first, naming the replacement. As of 1.5 every 2.0 change either warns or changes no call (the last column says which), and `modelly migrate --check-2.0` reports what a project must change. `modelly migrate --to 2.0` will rewrite what can be rewritten.

2.0 change

What you use today

Warns

The geographic space no longer holds the synthetic-population helpers (one home per feature)

modelly.population

from 1.4 (table above)

Everything deprecated in 1.3 to 1.6 is removed (H1)

the replacements in the table above

from the release that deprecated it

Per-agent random streams become the default (H6): agents draw from streams of their own, so a model without agent_streams draws other numbers for the same seed

set agent_streams = True now to get 2.0’s numbers; the 1.6 long-term-support line keeps 1.x’s

no warning: the numbers change, no call does; the migration guide and an agreement test cover it

One space protocol for grids, networks, continuous and geographic space (H2); property layers become fields on every space

today’s space classes, which stay as thin aliases through 2.x where they map cleanly

no warning in 1.x: no class goes in 2.0; one that does not map warns in 2.x before 3.0 removes it

Columns by default (H3): typed attributes become columns

Column(...) declarations

no warning: models keep their attributes

One clock (H4): steps are events at integer times, one documented tie-breaking order, one (compiled) scheduler

step, run_for, schedule_event keep their meaning

no warning: 1.x already orders events by time, priority, then insertion order, the 2.0 rule ([Event ordering](https://remipelloux.github.io/Modelly/dev/event_ordering.html))

Typed scenarios (H5): Scenario becomes a typed, validated base loadable from TOML and YAML

Scenario subclasses with annotated fields

from 1.5: an unannotated attribute, an undeclared parameter or a value of another type than its annotation warns (table above)

Checkpoint and result formats v2 (H8): 1.x checkpoints load through modelly checkpoint upgrade where their state maps

model.save / Model.load

no warning: 1.x files keep loading in 1.x

Python 3.13 minimum (H9): Python 3.12 is no longer supported

Python 3.12, 3.13 or 3.14

no warning: the package metadata says it

Provisional names (new in 1.3 and 1.4, see docs/api_stability.toml) are reviewed; the stable ones keep this policy (H10)

the name as it is

a provisional name that changes gets a changelog entry and, where it can, a warning

To see what your project must change, without running it:

```bash
modelly migrate --check-2.0 src/        # exit 1 when there is something to change
```

It reads every Python file and reports, with the line, each deprecated call and each Scenario attribute without an annotation, and as notes what changes without a warning: models without `agent_streams = True` (their numbers change in 2.0) and a `requires-python` below 3.13. To see what warns at run time, run the project with `python -W error::DeprecationWarning` (above).

## Deprecating something (for contributors)

```python
from modelly._deprecation import deprecated

def old_name(*args, **kwargs):
    deprecated("old_name()", "new_name()")
    return new_name(*args, **kwargs)
```

`stacklevel` counts from the caller of `deprecated`, like `warnings.warn` counts from its caller: the default (2) points the warning at whoever called `old_name`. In the same change, add the row to the table above, the entry to `modelly/_inventory.py` (the 2.0 inventory that `modelly migrate --check-2.0` reads, with the identifiers that find the old use in a project) and a changelog entry under “Deprecated”. `tests/test_inventory.py` fails when a `deprecated()` call, a table row and an inventory entry disagree.

The stability level of every public name (stable or provisional) is in [`docs/api_stability.toml`](https://github.com/RemiPelloux/Modelly/blob/main/docs/api_stability.toml): a stable name follows this policy; a provisional one (new in 1.3) may still change in a minor release, with a changelog entry.
