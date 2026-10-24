"""The grid-private cell class and how its cells pickle."""

from __future__ import annotations


def pickle_gridcell(obj):
    """Helper function for pickling GridCell instances."""
    # we have the base class and the state via __getstate__
    args = obj.__class__.__bases__[0], obj.__getstate__()
    return unpickle_gridcell, args


def unpickle_gridcell(parent, fields):
    """Helper function for unpickling GridCell instances."""
    # since the class is dynamically created, we recreate it here
    cell_klass = _make_grid_cell_class(parent)
    instance = cell_klass(
        (0, 0)
    )  # we use a default coordinate and overwrite it with the correct value next

    # __gestate__ returns a tuple with dict and slots, but slots contains the dict so we can just use the
    # second item only
    for k, v in fields[1].items():
        setattr(instance, k, v)

    return instance


def _make_grid_cell_class(parent: type) -> type:
    """Create the grid-private cell class that property-layer accessors are installed on.

    Pickling goes through ``__reduce__`` on the class itself rather than a global
    ``copyreg`` registration, so a discarded grid is not kept alive by the
    dispatch table.
    """
    return type(
        "GridCell",
        (parent,),
        {"property_layers": set(), "__slots__": (), "__reduce__": pickle_gridcell},
    )
