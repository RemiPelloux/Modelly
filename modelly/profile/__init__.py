"""Runtime profiling for Modelly models: where each step's time goes, in Modelly terms.

The runtime companion of ``python -m modelly.lint``. ``Profiler`` times each
step, every ``AgentSet.do`` / ``shuffle_do`` / ``map`` call by agent class and
method, ``DataCollector.collect`` and the scheduled-event callbacks, and counts
births and deaths per step::

    from modelly.profile import Profiler

    with Profiler(model) as prof:
        model.run_for(100)
    print(prof.report())

From a shell: ``python -m modelly.profile path/to/model.py:MyModel --steps 100``.
``compare_sizes`` builds the model at several population sizes and compares the
cost per agent (``--sizes 1000,4000`` on the command line).
Nothing is patched outside the ``with`` block. The guide is ``docs/profile.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modelly._optional import lazy_exports

if TYPE_CHECKING:
    from modelly.profile.profiler import Profiler, StepRecord
    from modelly.profile.sizes import SizeComparison, compare_sizes

__all__ = ["Profiler", "SizeComparison", "StepRecord", "compare_sizes"]

# Imported on first use: ``modelly.profile.loader`` (used by Studio and the web page)
# does not load the profiler.
__getattr__, __dir__ = lazy_exports(
    __name__,
    {
        "Profiler": "modelly.profile.profiler",
        "StepRecord": "modelly.profile.profiler",
        "SizeComparison": "modelly.profile.sizes",
        "compare_sizes": "modelly.profile.sizes",
    },
)
