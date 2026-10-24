"""Moving an agent between cells: compiled when available.

``set_cell`` is the setter of ``HasCell.cell``. It comes from the C module
``fastcell`` when it is built and not disabled (``MODELLY_PURE_PYTHON=1``),
else it is ``py_set_cell`` below. The C version makes the same calls in the
same order and raises the same exceptions; when a cell's ``add_agent`` or
``remove_agent`` is exactly ``Cell``'s own (see ``bind``), it runs that method's
body inline instead of calling it, and calls the method otherwise, so a Cell
subclass that overrides either one still gets its override.
``tests/native/test_cells.py`` runs both versions side by side.
"""

from __future__ import annotations

import os
from typing import Any

from modelly.core.exceptions import AgentMissingException, CellFullException


def py_set_cell(agent: Any, cell: Any) -> None:
    """Move ``agent`` to ``cell`` (None: out of its cell); add first, then remove."""
    old_cell = agent._modelly_cell

    # No-op if assigning to same cell
    if cell is old_cell:
        return

    # Attempt to add first
    if cell is not None:
        cell.add_agent(agent)

    if old_cell is not None:
        old_cell.remove_agent(agent)

    agent._modelly_cell = cell


def bind(cell_class: type) -> None:
    """Give the C version the reference ``add_agent``/``remove_agent`` it may inline."""
    if NATIVE:
        _fastcell.bind(
            cell_class.add_agent,
            cell_class.remove_agent,
            CellFullException,
            AgentMissingException,
        )


def _load() -> Any:
    """The compiled module, or None when absent or disabled."""
    if os.environ.get("MODELLY_PURE_PYTHON"):
        return None
    try:
        from modelly._native import fastcell  # noqa: PLC0415 - optional extension
    except ImportError:
        return None
    return fastcell


_fastcell = _load()
NATIVE: bool = _fastcell is not None
set_cell = _fastcell.set_cell if NATIVE else py_set_cell
