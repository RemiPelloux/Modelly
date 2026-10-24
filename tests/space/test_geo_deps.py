"""Optional geospatial dependencies fail with an error naming the extra."""

import importlib
import sys

import pytest

from modelly.space.geo._deps import require


def test_require_names_the_extra():
    """A missing module raises ImportError with the pip command for the extra."""
    with pytest.raises(ImportError, match=r"modelly-abm\[osm\]"):
        require("modelly_no_such_module", "osm")
    assert require("math", "geo") is importlib.import_module("math")


def test_geo_package_without_geopandas(monkeypatch):
    """Importing modelly.space.geo without GeoPandas points at the geo extra."""
    monkeypatch.setitem(sys.modules, "geopandas", None)
    for name in [m for m in sys.modules if m.startswith("modelly.space.geo")]:
        if name != "modelly.space.geo._deps":
            monkeypatch.delitem(sys.modules, name)
    with pytest.raises(ImportError, match=r"modelly-abm\[geo\]"):
        importlib.import_module("modelly.space.geo")
