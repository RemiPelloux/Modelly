"""DataRecorder for the DataRegistry Architecture.

This module orchestrates data collection from Modelly's DataRegistry, managing
storage and conversion to analysis-ready formats.

Architecture:
    DataRegistry → DataRecorder → Analysis

    - DataRegistry: Pure extraction (what to collect)
    - DataRecorders: Storage orchestration (efficient accumulation) derived from BaseDataRecorder
    - Observable-based auto-collection - subscribes to model.time observable

The recorder backends live in their own modules; this module re-exports them.
"""

from modelly.data.recorders.config import DatasetConfig
from modelly.data.recorders.json_recorder import JSONDataRecorder, NumpyJSONEncoder
from modelly.data.recorders.memory import DataRecorder, DatasetStorage
from modelly.data.recorders.parquet import ParquetDataRecorder
from modelly.data.recorders.sql import SQLDataRecorder

__all__ = [
    "DataRecorder",
    "DatasetConfig",
    "DatasetStorage",
    "JSONDataRecorder",
    "NumpyJSONEncoder",
    "ParquetDataRecorder",
    "SQLDataRecorder",
]
