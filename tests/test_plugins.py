"""Plugin discovery through entry points, with fake distributions on sys.path."""

import sys

import pytest

from modelly.plugins import GROUPS, PluginError, discover, load_all

MODULE = "fake_modelly_plugin"


def install(root, dist, entry_points, module_source=None):
    """Write a ``<dist>-1.0.dist-info`` with ``entry_points`` and, optionally, a module."""
    info = root / f"{dist}-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {dist}\nVersion: 1.0\n", encoding="utf-8"
    )
    lines = []
    for group, entries in entry_points.items():
        lines.append(f"[{group}]")
        lines += [f"{name} = {value}" for name, value in entries.items()]
    (info / "entry_points.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if module_source is not None:
        (root / f"{MODULE}.py").write_text(module_source, encoding="utf-8")


@pytest.fixture
def fake_site(tmp_path, monkeypatch):
    """A folder on sys.path holding two fake distributions."""
    install(
        tmp_path,
        "fakeplug",
        {
            "modelly.spaces": {"ring": f"{MODULE}:Ring", "broken": "no_such_module:X"},
            "modelly.samplers": {"halton": f"{MODULE}:halton"},
        },
        "LOADS = []\nLOADS.append(1)\n\nclass Ring:\n    pass\n\n\ndef halton():\n    return 0\n",
    )
    install(tmp_path, "zzplug", {"modelly.spaces": {"ring": "elsewhere:Ring"}})
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, MODULE, raising=False)
    yield tmp_path
    sys.modules.pop(MODULE, None)


def test_groups_are_documented_names():
    """The groups Modelly defines."""
    assert "modelly.spaces" in GROUPS
    assert "modelly.lint_rules" in GROUPS
    assert len(set(GROUPS)) == len(GROUPS)


def test_discover_is_lazy_and_sorted(fake_site):
    """Discovery imports nothing; plugins are sorted by name."""
    with pytest.warns(RuntimeWarning, match="zzplug"):
        spaces = discover("modelly.spaces")
    assert list(spaces) == ["broken", "ring"]
    assert MODULE not in sys.modules
    ring = spaces["ring"]
    assert ring.distribution == "fakeplug"
    assert ring.value == f"{MODULE}:Ring"
    assert ring.load().__name__ == "Ring"
    assert ring.load() is ring()  # loaded once, cached
    assert sys.modules[MODULE].LOADS == [1]


def test_a_broken_plugin_is_isolated(fake_site):
    """One plugin failing to import does not stop the others."""
    with pytest.warns(RuntimeWarning):
        loaded, errors = load_all("modelly.spaces")
    assert list(loaded) == ["ring"]
    assert list(errors) == ["broken"]
    assert isinstance(errors["broken"], PluginError)
    assert isinstance(errors["broken"].__cause__, ModuleNotFoundError)
    assert "fakeplug" in str(errors["broken"])
    with pytest.warns(RuntimeWarning), pytest.raises(PluginError, match="broken"):
        discover("modelly.spaces")["broken"].load()


def test_other_groups_and_unknown_group(fake_site):
    """Every group is independent; an unknown group is empty."""
    samplers = discover("modelly.samplers")
    assert samplers["halton"].load()() == 0
    assert discover("modelly.studio_views") == {}
    assert discover("not.a.group") == {}
