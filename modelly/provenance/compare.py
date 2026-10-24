"""Find the first place where two runs' output tables differ.

Numeric columns are compared with ``numpy.isclose`` under the given tolerances (both 0
by default: the values must be identical); other columns must be equal. Missing values
match missing values.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Difference:
    """Where an output differs: table, then column and row when the shapes agree."""

    table: str
    message: str
    column: str | None = None
    row: int | None = None

    def __str__(self) -> str:
        """``table 'model', column 'Gini', row 12: expected 0.4, got 0.5``."""
        where = [f"table {self.table!r}"]
        if self.column is not None:
            where.append(f"column {self.column!r}")
        if self.row is not None:
            where.append(f"row {self.row}")
        return f"{', '.join(where)}: {self.message}"


@dataclass(frozen=True)
class Tolerance:
    """Relative and absolute tolerance for numeric columns."""

    rtol: float = 0.0
    atol: float = 0.0


def _numeric(series: pd.Series) -> bool:
    """True for int and float columns (bool and object columns compare exactly)."""
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(
        series
    )


def _equal(expected: pd.Series, actual: pd.Series, tolerance: Tolerance) -> np.ndarray:
    """A boolean array: where the two columns agree."""
    if _numeric(expected) and _numeric(actual):
        return np.isclose(
            actual.to_numpy(dtype=float),
            expected.to_numpy(dtype=float),
            rtol=tolerance.rtol,
            atol=tolerance.atol,
            equal_nan=True,
        )
    both_missing = expected.isna().to_numpy() & actual.isna().to_numpy()
    same = expected.astype(object).to_numpy() == actual.astype(object).to_numpy()
    return np.asarray(same, dtype=bool) | both_missing


def _shape_difference(
    table: str, expected: pd.DataFrame, actual: pd.DataFrame
) -> Difference | None:
    """A difference in the columns or the number of rows, if any."""
    want, got = [str(c) for c in expected.columns], [str(c) for c in actual.columns]
    if want != got:
        missing = sorted(set(want) - set(got))
        extra = sorted(set(got) - set(want))
        return Difference(
            table,
            f"columns differ: expected {want}, got {got} "
            f"(missing {missing}, extra {extra})",
        )
    if len(expected) != len(actual):
        return Difference(
            table, f"row counts differ: expected {len(expected)}, got {len(actual)}"
        )
    return None


def first_difference(
    table: str,
    expected: pd.DataFrame,
    actual: pd.DataFrame,
    tolerance: Tolerance = Tolerance(),  # noqa: B008  (frozen, immutable)
) -> Difference | None:
    """The first differing column, row and values of one table, or None if they match.

    Columns are scanned in table order and rows top to bottom; the reported row is the
    row's position (0-based) in the table.
    """
    shape = _shape_difference(table, expected, actual)
    if shape is not None:
        return shape
    for column in expected.columns:
        agree = _equal(expected[column], actual[column], tolerance)
        if agree.all():
            continue
        row = int(np.argmin(agree))
        message = (
            f"expected {expected[column].iloc[row]!r}, got {actual[column].iloc[row]!r}"
        )
        return Difference(table, message, column=str(column), row=row)
    return None
