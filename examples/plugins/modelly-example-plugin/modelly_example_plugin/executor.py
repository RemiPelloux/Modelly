"""An executor that runs an experiment's tasks one by one, in order, in this process."""

from __future__ import annotations

from modelly.experiments.executors.local import SerialExecutor


class InOrderExecutor(SerialExecutor):
    """``executor="in_order"``: Modelly's serial executor under the plugin's name."""

    name = "in_order"
