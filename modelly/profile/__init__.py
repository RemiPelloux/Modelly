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

from modelly.profile.profiler import Profiler, StepRecord
from modelly.profile.sizes import SizeComparison, compare_sizes

__all__ = ["Profiler", "SizeComparison", "StepRecord", "compare_sizes"]
