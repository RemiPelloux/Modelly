"""Tables for the DataCollector: named columns that model code appends rows to."""

from modelly.core.exceptions import TableMissingException


class TableMixin:
    """Create tables and append rows to them; rows are stored column-wise in self.tables."""

    def _new_table(self, table_name, table_columns):
        """Add a new table that objects can write to.

        Args:
            table_name: Name of the new table.
            table_columns: List of columns to add to the table.
        """
        new_table = {column: [] for column in table_columns}
        self.tables[table_name] = new_table

    def add_table_row(self, table_name, row, ignore_missing=False):
        """Add a row dictionary to a specific table.

        A row with missing required columns leaves the table unchanged.

        Args:
            table_name: Name of the table to append a row to.
            row: A dictionary of the form {column_name: value...}
            ignore_missing: If True, fill any missing columns with Nones;
                            if False, throw an error if any columns are missing
        """
        if table_name not in self.tables:
            raise TableMissingException(table_name)

        table = self.tables[table_name]
        if not ignore_missing:
            for column in table:
                if column not in row:
                    raise ValueError(
                        f"Could not insert row with missing column '{column}'"
                    )

        for column, values in table.items():
            values.append(row.get(column))
