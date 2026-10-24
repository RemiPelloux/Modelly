"""Tests for the Ray executor against a stand-in for Ray's public task API.

The stand-in runs each remote call when ``ray.get`` asks for it, so the
executor's bookkeeping (init, in-flight limit, wait, shutdown) is exercised
without a Ray installation. With Ray installed, one test runs it for real.
"""

import sys
import types

import pytest

from tests.experiments.executors.shared import experiment

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")


class FakeRay(types.ModuleType):
    """The part of Ray's API the executor uses, recording what it was asked."""

    def __init__(self, initialized=False):  # noqa: D107
        super().__init__("ray")
        self.initialized, self.calls, self.in_flight = initialized, [], []

    def is_initialized(self):  # noqa: D102
        return self.initialized

    def init(self, address=None, **options):  # noqa: D102
        self.initialized = True
        self.calls.append(("init", address, options))

    def shutdown(self):  # noqa: D102
        self.initialized = False
        self.calls.append(("shutdown",))

    def remote(self, function):  # noqa: D102
        ray = self

        class Remote:
            def remote(self, *args):
                ref = (function, args)
                ray.in_flight.append(ref)
                return ref

        return Remote()

    def wait(self, refs, num_returns=1):  # noqa: D102
        self.calls.append(("wait", len(refs)))
        return refs[:num_returns], refs[num_returns:]

    def get(self, ref):  # noqa: D102
        function, args = ref
        return function(*args)


@pytest.fixture
def serial_frame(tmp_path):
    """The reference results, run in this process."""
    reference = experiment(tmp_path / "serial")
    reference.run("serial")
    return reference.results().df()


def test_runs_through_the_task_api(monkeypatch, tmp_path, serial_frame):
    """Ray starts, keeps max_parallel tasks in flight, shuts down; results match."""
    fake = FakeRay()
    monkeypatch.setitem(sys.modules, "ray", fake)
    run = experiment(tmp_path / "ray")
    report = run.run("ray", max_parallel=3, num_cpus=2)
    assert report.ok and report.done == 8
    assert fake.calls[0] == ("init", None, {"num_cpus": 2})
    assert fake.calls[-1] == ("shutdown",)
    assert max(call[1] for call in fake.calls if call[0] == "wait") == 3
    assert run.results().df().equals(serial_frame)


def test_an_initialised_ray_is_left_running(monkeypatch, tmp_path):
    """When Ray is already up, the executor neither inits nor shuts it down."""
    fake = FakeRay(initialized=True)
    monkeypatch.setitem(sys.modules, "ray", fake)
    assert experiment(tmp_path).run("ray", address="auto").ok
    assert not [call for call in fake.calls if call[0] in ("init", "shutdown")]


def test_missing_ray_names_the_extra(monkeypatch, tmp_path):
    """Without Ray the error says which extra to install."""
    monkeypatch.setitem(sys.modules, "ray", None)
    with pytest.raises(ImportError, match=r"modelly-abm\[ray\]"):
        experiment(tmp_path).run("ray")


def test_real_ray(tmp_path, serial_frame):
    """With Ray installed, a local Ray gives the serial numbers."""
    if isinstance(sys.modules.get("ray"), FakeRay):
        sys.modules.pop("ray")
    pytest.importorskip("ray")
    run = experiment(tmp_path / "real")
    assert run.run("ray", max_parallel=2, num_cpus=2).ok
    assert run.results().df().equals(serial_frame)
