"""DataFrame exports for the DataCollector.

The DataCollector stores what it collects in plain dictionaries and lists;
this mixin turns those collections into pandas DataFrames on request.
"""

import contextlib
import itertools
import warnings

from modelly.core.exceptions import TableMissingException

with contextlib.suppress(ImportError):
    import pandas as pd


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

        steps = list(self._agent_records.values())
        cached = self._agent_frame_cache
        done = cached[0] if cached is not None and cached[0] <= len(steps) else 0
        new_rows = itertools.chain.from_iterable(steps[done:])
        frame = pd.DataFrame.from_records(
            data=list(new_rows),
            columns=["Step", "AgentID", *self.agent_reporters],
            index=["Step", "AgentID"],
        )
        if done:
            frame = pd.concat([cached[1], frame])
        self._agent_frame_cache = (len(steps), frame)
        return frame

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

        rep_names = list(self.agenttype_reporters[agent_type])
        return pd.DataFrame.from_records(
            data=self._agenttype_rows(agent_type),
            columns=["Step", "AgentID", *rep_names],
            index=["Step", "AgentID"],
        )

    def _agenttype_rows(self, agent_type):
        """Return every collected row for agent_type, across all steps, as a list."""
        # Materialize to a list: passing an empty generator to
        # pd.DataFrame.from_records with an index misparses the index labels as
        # rows (producing spurious all-NaN rows), whereas an empty list does not.
        # Empty results are normal now that agenttype collection is exact-type.
        return list(
            itertools.chain.from_iterable(
                records[agent_type]
                for records in self._agenttype_records.values()
                if agent_type in records
            )
        )

    def get_table_dataframe(self, table_name):
        """Create a pandas DataFrame from a particular table.

        Args:
            table_name: The name of the table to convert.
        """
        if table_name not in self.tables:
            raise TableMissingException(table_name)
        return pd.DataFrame(self.tables[table_name])
