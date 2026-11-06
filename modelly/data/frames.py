"""DataFrame exports for the DataCollector.

The DataCollector stores what it collects in plain dictionaries and lists;
this mixin turns those collections into pandas DataFrames on request.
"""

import warnings

from modelly._optional import LazyModule
from modelly.core.exceptions import TableMissingException
from modelly.data._records import FrameCache, growing_frame, records_frame

pd = LazyModule("pandas")


class DataFrameExportMixin:
    """Build pandas DataFrames from the records a DataCollector holds."""

    def get_model_vars_dataframe(self):
        """Create a pandas DataFrame from the model variables.

        The DataFrame has one column for each model variable, and the index is
        (implicitly) the model tick.
        """
        # Check if self.model_reporters dictionary is empty, if so warn
        if not self.model_reporters:
            warnings.warn(
                "No model reporters have been defined in the DataCollector, returning empty DataFrame.",
                UserWarning,
                stacklevel=2,
            )
            return pd.DataFrame()

        return pd.DataFrame(self.model_vars)

    def get_agent_vars_dataframe(self):
        """Create a pandas DataFrame from the agent variables.

        The DataFrame has one column for each variable, with two additional
        columns for tick and agent_id.
        """
        # Check if self.agent_reporters dictionary is empty, if so warn
        if not self.agent_reporters:
            warnings.warn(
                "No agent reporters have been defined in the DataCollector, returning empty DataFrame.",
                UserWarning,
                stacklevel=2,
            )
            return pd.DataFrame()

        cache = getattr(self, "_agent_frame_cache", None)
        if not isinstance(cache, FrameCache):  # e.g. a collector pickled by 1.5.0
            cache = self._agent_frame_cache = FrameCache()
        records = list(self._agent_records.values())
        return growing_frame(cache, records, list(self.agent_reporters))

    def get_agenttype_vars_dataframe(self, agent_type):
        """Create a pandas DataFrame from the agent-type variables for a specific agent type.

        The DataFrame has one column for each variable, with two additional
        columns for tick and agent_id.

        Args:
            agent_type: The type of agent to get the data for.
        """
        # Check if self.agenttype_reporters dictionary is empty for this agent type, if so return empty DataFrame
        if agent_type not in self.agenttype_reporters:
            warnings.warn(
                f"No agent-type reporters have been defined for {agent_type} in the DataCollector, returning empty DataFrame.",
                UserWarning,
                stacklevel=2,
            )
            return pd.DataFrame()

        records = [
            by_type[agent_type]
            for by_type in self._agenttype_records.values()
            if agent_type in by_type
        ]
        return records_frame(records, list(self.agenttype_reporters[agent_type]))

    def get_table_dataframe(self, table_name):
        """Create a pandas DataFrame from a particular table.

        Args:
            table_name: The name of the table to convert.
        """
        if table_name not in self.tables:
            raise TableMissingException(table_name)
        return pd.DataFrame(self.tables[table_name])
