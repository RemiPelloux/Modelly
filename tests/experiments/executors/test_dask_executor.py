"""Tests for the Dask executor: a local cluster gives the serial results."""

import pytest

from tests.experiments.executors.shared import MAX_PARALLEL, experiment

distributed = pytest.importorskip("distributed")
pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")


@pytest.fixture(scope="module")
def serial_frame(tmp_path_factory):
    """The reference results, run in this process."""
    reference = experiment(tmp_path_factory.mktemp("serial"))
    reference.run("serial")
    return reference.results().df()


def test_local_cluster_matches_serial(tmp_path, serial_frame):
    """The executor's own two-process local cluster gives the serial numbers."""
    run = experiment(tmp_path)
    report = run.run("dask", max_parallel=MAX_PARALLEL)
    assert report.ok and report.done == 8
    assert run.results().df().equals(serial_frame)


def test_existing_client_and_address(tmp_path, serial_frame):
    """A given client is used and left open; an address is connected to and closed."""
    with (
        distributed.LocalCluster(
            n_workers=1, processes=False, dashboard_address=None
        ) as cluster,
        distributed.Client(cluster) as client,
    ):
        first = experiment(tmp_path / "client")
        assert first.run("dask", max_parallel=1, client=client).ok
        assert client.status == "running"
        second = experiment(tmp_path / "address")
        assert second.run("dask", address=cluster.scheduler_address).ok
    assert first.results().df().equals(serial_frame)
    assert second.results().df().equals(serial_frame)
