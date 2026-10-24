"""Modelly Studio: run a model in the browser, change it live, scrub through time.

``modelly studio path/to/model.py:Model`` serves a Solara app on localhost and opens the
default browser. The app is built from these parts:

- ``config``: ``StudioConfig``, what one server shows;
- ``params``: the parameter panel's fields, read from the model's ``Scenario``;
- ``loader``: the model class and the portrayal a command line names;
- ``session``: ``StudioSession``, one tab's run (build, step, profile, scrub, replay, lint);
- ``timeline``: checkpoints through ``modelly.timetravel``, or a replay when the model
  cannot be checkpointed;
- ``data``: series, agent table, figures and the files the exports download;
- ``state``, ``panels``, ``views``, ``tools`` and ``app``: the Solara components.

The guide is ``docs/studio.md``. This package imports Solara only in the modules that draw;
the names exported here work without the ``viz`` extra.
"""

from modelly.studio.config import StudioConfig
from modelly.studio.loader import load_model_class, load_portrayal
from modelly.studio.params import Parameter, parameters_of

__all__ = [
    "Parameter",
    "StudioConfig",
    "load_model_class",
    "load_portrayal",
    "parameters_of",
]
