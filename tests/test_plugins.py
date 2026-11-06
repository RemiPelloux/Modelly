"""Plugin discovery through entry points, with fake distributions on sys.path."""

import os
import sys

import pytest

from modelly import plugins
from modelly.plugins import GROUPS, PluginError, discover, load_all

MODULE = "fake_modelly_plugin"
LATER_NS = 1_000_000_000  # one second


def install(root, dist, entry_points, module_source=None, requires=()):
    """Write a ``<dist>-1.0.dist-info`` with ``entry_points`` and, optionally, a module."""
    info = root / f"{dist}-1.0.dist-info"
    info.mkdir()
    lines = "".join(f"Requires-Dist: {entry}\n" for entry in requires)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {dist}\nVersion: 1.0\n{lines}", encoding="utf-8"
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


@pytest.mark.parametrize(
    ("requires", "declared", "compatible"),
    [
        ((), None, True),
        (("numpy", "modelly-abm>=1.0,<99"), ">=1.0,<99", True),
        (("Modelly_ABM (<1.0)",), "<1.0", False),
        (("modelly-abm<1.0 ; extra == 'old'",), None, True),
    ],
)
def test_a_plugin_declares_the_modelly_it_supports(
    tmp_path, monkeypatch, requires, declared, compatible
):
    """The requirement on modelly-abm is read; an excluded version refuses to load."""
    install(
        tmp_path, "verplug", {"modelly.samplers": {"v": "json:dumps"}}, None, requires
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    plugin = discover("modelly.samplers")["v"]
    assert (plugin.requires, plugin.compatible) == (declared, compatible)
    if compatible:
        assert callable(plugin.load())
    else:
        with pytest.raises(PluginError, match=r"requires modelly-abm<1\.0"):
            plugin.load()
        assert set(load_all("modelly.samplers")[1]) == {"v"}


def test_modelly_plugins_reports_and_checks(fake_site, capsys):
    """``modelly plugins`` lists every group; ``--check`` fails on the broken plugin."""
    from modelly._plugins_cli import main  # noqa: PLC0415

    with pytest.warns(RuntimeWarning):
        assert main([]) == 0
    out = capsys.readouterr().out
    assert "modelly.spaces: 2" in out and "modelly.executors: none" in out
    with pytest.warns(RuntimeWarning):
        assert main(["--check"]) == 1
    assert "fails to load" in capsys.readouterr().out


def test_scan_is_kept_until_a_package_is_installed(tmp_path, monkeypatch):
    """The entry points are scanned once; installing into a path folder rescans."""
    monkeypatch.syspath_prepend(str(tmp_path))
    assert discover("modelly.samplers") == {}
    first = plugins._installed_entry_points()
    assert plugins._installed_entry_points() is first
    install(tmp_path, "lateplug", {"modelly.samplers": {"late": "json:dumps"}})
    # A distinct modification time, as a real install leaves (timestamps are coarse).
    stamp = tmp_path.stat().st_mtime_ns + LATER_NS
    os.utime(tmp_path, ns=(stamp, stamp))
    assert list(discover("modelly.samplers")) == ["late"]
    plugins.clear_cache()
    assert plugins._installed_entry_points() is not first
