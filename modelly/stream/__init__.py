"""Live data for running models (provisional, 1.4).

Sources hand out observations as they arrive (``ReplaySource``, ``CSVSource``,
``HTTPSource``, and ``MQTTSource`` and ``KafkaSource`` with their extras); an
``ObservationOperator`` reads the same quantities from a model, so a run can
be compared with the world step by step.

Data assimilation works on an ``Ensemble`` of replicates advanced in lock
step: a ``ParticleFilter`` (Gordon et al. 1993) weights and resamples them, an
``EnsembleKalmanFilter`` (Evensen 1994, 2003) adjusts continuous parameters.
Both give quantile bands now and ahead as DataFrames.
"""

from modelly.stream.connectors import KafkaSource, MQTTSource
from modelly.stream.ensemble import Ensemble
from modelly.stream.kalman import EnsembleKalmanFilter
from modelly.stream.operators import ObservationOperator
from modelly.stream.particle import FilterStep, ParticleFilter
from modelly.stream.sources import CSVSource, HTTPSource, Observation, ReplaySource

__all__ = [
    "CSVSource",
    "Ensemble",
    "EnsembleKalmanFilter",
    "FilterStep",
    "HTTPSource",
    "KafkaSource",
    "MQTTSource",
    "Observation",
    "ObservationOperator",
    "ParticleFilter",
    "ReplaySource",
]
