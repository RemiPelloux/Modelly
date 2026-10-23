"""Test if namespsaces importing work better."""

import pytest


def test_import():
    """This tests the new, simpler Modelly namespace.

    See https://github.com/RemiPelloux/Modelly/pull/1294.
    """
    import modelly  # noqa: PLC0415
    from modelly.datacollection import DataCollector  # noqa: PLC0415

    _ = DataCollector
    _ = modelly.DataCollector


def test_simulator_classes_removed():
    """Simulator, ABMSimulator, and DEVSimulator must stay removed.

    Modelly schedules events on the Model itself and ships no ``devs`` package.
    This pins the exact error a user hits so it can't silently regress, and so it stays
    consistent with the migration guide.
    """
    import modelly  # noqa: PLC0415

    with pytest.raises(ModuleNotFoundError):
        import modelly.experimental.devs  # noqa: PLC0415

    with pytest.raises(ModuleNotFoundError):
        from modelly.experimental.devs.simulator import (  # noqa: F401, PLC0415
            ABMSimulator,
        )

    with pytest.raises(ModuleNotFoundError):
        from modelly.experimental.devs.simulator import (  # noqa: F401, PLC0415
            DEVSimulator,
        )

    for name in ("Simulator", "ABMSimulator", "DEVSimulator"):
        assert not hasattr(modelly, name)


def test_simulator_replacement_api_present():
    """The scheduling API that replaced the Simulator classes must exist.

    ``Model.run_for``/``run_until``/``schedule_event``/``schedule_recurring``
    and the ``modelly.time`` primitives are what the migration guide points
    users to; this fails loudly if any of them are renamed or dropped.
    """
    import modelly  # noqa: PLC0415

    for method in (
        "run_for",
        "run_until",
        "schedule_event",
        "schedule_recurring",
    ):
        assert hasattr(modelly.Model, method)

    for name in ("Event", "EventGenerator", "EventList", "Priority", "Schedule"):
        assert hasattr(modelly.time, name)


def test_meta_agents():
    """Meta-agents live at modelly.experimental.meta_agents."""
    import modelly  # noqa: PLC0415

    assert hasattr(modelly.experimental, "meta_agents")
    from modelly.experimental.meta_agents import MetaAgents  # noqa: PLC0415

    assert MetaAgents is modelly.experimental.meta_agents.MetaAgents


def test_import_modelly_does_not_load_scipy():
    """Importing modelly leaves scipy unloaded until a KD-tree or cdist is needed."""
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    code = "import modelly, sys; print(any(m.startswith('scipy') for m in sys.modules))"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"
