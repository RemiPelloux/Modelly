"""New style data collection."""

from modelly.data.recorders.base import BaseDataRecorder
from modelly.data.recorders.config import DatasetConfig
from modelly.data.recorders.json_recorder import JSONDataRecorder
from modelly.data.recorders.memory import DataRecorder
from modelly.data.recorders.numpy_dataset import NumpyAgentDataSet
from modelly.data.recorders.object_datasets import (
    AgentDataSet,
    ModelDataSet,
    TableDataSet,
)
from modelly.data.recorders.parquet import ParquetDataRecorder
from modelly.data.recorders.protocol import DataSet
from modelly.data.recorders.registry import DataRegistry
from modelly.data.recorders.sql import SQLDataRecorder

__all__ = [
    "AgentDataSet",
    "BaseDataRecorder",
    "DataRecorder",
    "DataRegistry",
    "DataSet",
    "DatasetConfig",
    "JSONDataRecorder",
    "ModelDataSet",
    "NumpyAgentDataSet",
    "ParquetDataRecorder",
    "SQLDataRecorder",
    "TableDataSet",
]
