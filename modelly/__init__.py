"""Modelly Agent-Based Modeling Framework.

Core Objects: Model, and Agent.
"""

import datetime

import modelly.discrete_space as discrete_space
import modelly.experimental as experimental
import modelly.time as time
from modelly.agent import Agent
from modelly.columns import Column
from modelly.datacollection import DataCollector
from modelly.model import Model

__all__ = [
    "Agent",
    "Column",
    "DataCollector",
    "Model",
    "discrete_space",
    "experimental",
    "time",
]

__title__ = "modelly"
__version__ = "1.3.1"
__license__ = "Apache 2.0"
_this_year = datetime.datetime.now(tz=datetime.UTC).date().year
__copyright__ = f"Copyright {_this_year} Modelly Team"
