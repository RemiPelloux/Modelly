"""Modelly Agent-Based Modeling Framework.

Core Objects: Model, and Agent.
"""

import datetime

import modelly.behaviour as behaviour
import modelly.data as data
import modelly.scenarios as scenarios
import modelly.space as space
import modelly.time as time
from modelly.batch import CohortTable, run_batch, run_grid
from modelly.core import Agent, Column, FastRandom, Model
from modelly.data import DataCollector

__all__ = [
    "Agent",
    "CohortTable",
    "Column",
    "DataCollector",
    "FastRandom",
    "Model",
    "behaviour",
    "data",
    "run_batch",
    "run_grid",
    "scenarios",
    "space",
    "time",
]

__title__ = "modelly"
__version__ = "1.4.2"
__license__ = "Apache 2.0"
_this_year = datetime.datetime.now(tz=datetime.UTC).date().year
__copyright__ = f"Copyright {_this_year} Modelly Team"
