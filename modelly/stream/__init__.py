"""Live data for running models (provisional, 1.4).

Sources hand out observations as they arrive (``ReplaySource``, ``CSVSource``,
``HTTPSource``); an ``ObservationOperator`` reads the same quantities from a
model, so a run can be compared with the world step by step. Data assimilation
over replicate ensembles builds on these.
"""

from modelly.stream.operators import ObservationOperator
from modelly.stream.sources import CSVSource, HTTPSource, Observation, ReplaySource

__all__ = [
    "CSVSource",
    "HTTPSource",
    "Observation",
    "ObservationOperator",
    "ReplaySource",
]
