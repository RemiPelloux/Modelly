"""An example third-party plugin for Modelly, one entry point in every group.

Each module is imported only when Modelly loads its entry point:

- ``space.Ring`` (``modelly.spaces``): a ring of cells, a network space;
- ``sampler.uniform`` (``modelly.samplers``): plain random designs for experiments;
- ``collector.share_of`` (``modelly.collectors``): a reporter factory;
- ``executor.InOrderExecutor`` (``modelly.executors``): runs an experiment in order;
- ``lint.NO_PRINT`` (``modelly.lint_rules``): a ``modelly lint`` rule, EXP001;
- ``studio.ScenarioView`` (``modelly.studio_views``): a Studio tab.
"""
