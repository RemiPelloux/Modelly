"""Tests for the executor registry: names, options, plugins through entry points."""

from importlib.metadata import EntryPoint

import pytest

from modelly.experiments import executors
from modelly.experiments.executors import (
    ENTRY_POINT_GROUP,
    Executor,
    available_executors,
    get_executor,
    register_executor,
)
from modelly.experiments.executors.local import SerialExecutor


class Custom(Executor):
    """A do-nothing executor for the registry tests."""

    name = "custom"


def test_builtin_names():
    """Every executor of the roadmap is available by name."""
    names = set(available_executors())
    assert {"serial", "threads", "processes", "dask", "ray", "slurm", "pbs"} <= names
    assert isinstance(get_executor("serial"), SerialExecutor)


def test_unknown_names_and_options():
    """An unknown name lists the available ones; unknown options are an error."""
    with pytest.raises(ValueError, match="available: "):
        get_executor("nope")
    with pytest.raises(TypeError, match="takes no option"):
        get_executor("threads", partition="short")
    instance = SerialExecutor()
    assert get_executor(instance) is instance
    with pytest.raises(TypeError, match="constructor"):
        get_executor(instance, address="x")


def test_register_executor(monkeypatch):
    """register_executor adds a name."""
    monkeypatch.setattr(executors, "_REGISTRY", {})
    register_executor("custom", Custom)
    assert isinstance(get_executor("custom"), Custom)
    assert "custom" in available_executors()


def test_entry_point_plugins(monkeypatch):
    """An entry point in modelly.executors is found by name."""
    point = EntryPoint(
        "plugin", "tests.experiments.executors.test_registry:Custom", ENTRY_POINT_GROUP
    )
    monkeypatch.setattr(executors, "entry_points", lambda group: [point])
    assert isinstance(get_executor("plugin"), Custom)
    assert "plugin" in available_executors()


def test_base_executor_runs_nothing():
    """The base class leaves run to subclasses and accepts empty task lists."""
    with pytest.raises(NotImplementedError):
        Executor().run([])
    Executor().check([])
