"""Test if namespsaces importing work better."""

import pytest


def test_import():
    """This tests the new, simpler Modelly namespace.

    See https://github.com/RemiPelloux/Modelly/pull/1294.
    """
    import modelly  # noqa: PLC0415
    from modelly.data.collector import DataCollector  # noqa: PLC0415

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
        import modelly.experimental.devs  # noqa: F401, PLC0415

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
    """Meta-agents live at modelly.behaviour.meta_agents."""
    import modelly  # noqa: PLC0415

    assert hasattr(modelly.behaviour, "meta_agents")
    from modelly.behaviour.meta_agents import MetaAgents  # noqa: PLC0415

    assert MetaAgents is modelly.behaviour.meta_agents.MetaAgents


@pytest.mark.parametrize(
    "old",
    [
        "modelly.experimental",
        "modelly.discrete_space",
        "modelly.visualization",
        "modelly.agentset",
        "modelly.datacollection",
    ],
)
def test_pre_2_0_packages_are_gone(old):
    """2.0 moved every module into a domain package; the old paths do not import."""
    import importlib  # noqa: PLC0415

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(old)


def test_domain_packages_export_their_public_names():
    """Each domain package re-exports what users import from it."""
    import modelly  # noqa: PLC0415

    assert modelly.core.Agent is modelly.Agent
    assert modelly.data.DataCollector is modelly.DataCollector
    assert modelly.batch.run_batch is modelly.run_batch
    for name in ("Cell", "CellAgent", "OrthogonalMooreGrid", "Network", "VoronoiGrid"):
        assert hasattr(modelly.space, name)


def test_import_modelly_does_not_load_scipy():
    """Importing modelly leaves scipy unloaded until a KD-tree or cdist is needed."""
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    code = "import modelly, sys; print(any(m.startswith('scipy') for m in sys.modules))"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"
