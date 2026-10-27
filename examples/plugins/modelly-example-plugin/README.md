# modelly-example-plugin

A third-party plugin for Modelly with one entry point in every group Modelly reads
(`pyproject.toml`). Install it next to Modelly:

```bash
pip install -e examples/plugins/modelly-example-plugin
```

| Group | Entry point | What Modelly does with it |
|---|---|---|
| `modelly.spaces` | `ring`: `Ring(n)`, a ring of cells | `discover("modelly.spaces")["ring"].load()` gives the class |
| `modelly.samplers` | `uniform`: `uniform(n)`, random designs | `[design] kind = "uniform"` in an experiment file |
| `modelly.collectors` | `share_of`: a reporter factory | `discover("modelly.collectors")["share_of"].load()` gives the factory |
| `modelly.executors` | `in_order`: a serial executor | `experiment.run(executor="in_order")` |
| `modelly.lint_rules` | `no_print`: rule EXP001 | `modelly lint` reports `print()` calls |
| `modelly.studio_views` | `Scenario`: a Studio tab | `modelly studio` shows a "Scenario" tab |

`tests/test_example_plugin.py` registers this folder as an installed distribution and checks
each one. The guide is `docs/plugins.md`.
