"""Tests for Cluster and DistributedModel: collectors, checkpoints and backends."""

import importlib.util
import json

import pytest

from modelly.core.exceptions import CheckpointError
from modelly.distributed import Cluster, partition, single_process, snapshot
from modelly.examples.distributed.grid_epidemic import EpidemicScenario, GridEpidemic
from modelly.examples.distributed.network_sir import NetworkScenario, NetworkSIR

STEPS = 6
GRID = {"width": 20, "height": 20, "people": 300, "infected": 8}
SPLIT = partition.grid_blocks(2, 2)


def _scenario(seed=4):
    """A small grid epidemic scenario."""
    return EpidemicScenario(rng=seed, **GRID)


def test_collect_reduces_reporters_across_partitions():
    """collect() has one row per step and the build, summed over partitions."""
    reference = single_process(GridEpidemic, _scenario(), STEPS)
    with Cluster("local") as cluster:
        model = cluster.build(GridEpidemic, _scenario(), SPLIT)
        model.run_for(STEPS)
        frame = cluster.collect()
        assert model.partitions == SPLIT.partitions
        assert model.time == STEPS
    assert frame.equals(reference.rows)
    assert (frame[["S", "I", "R"]].sum(axis=1) == GRID["people"]).all()


def test_snapshot_equals_the_single_process_snapshot():
    """The gathered snapshot is the one-process snapshot, row for row."""
    model = GridEpidemic(_scenario())
    for _ in range(STEPS):
        model.step()
    expected = snapshot(model, ("state", "days"))
    with Cluster("local") as cluster:
        split = cluster.build(GridEpidemic, _scenario(), SPLIT)
        split.run_for(STEPS)
        assert split.snapshot(("state", "days")).equals(expected)


def test_checkpoint_and_restore_continue_the_run(tmp_path):
    """A restored split run continues draw for draw: same rows and states."""
    reference = single_process(GridEpidemic, _scenario(), 2 * STEPS)
    with Cluster("local") as cluster:
        model = cluster.build(GridEpidemic, _scenario(), SPLIT)
        model.run_for(STEPS)
        model.checkpoint(tmp_path)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["partitions"] == SPLIT.partitions
    assert len(list(tmp_path.glob("part-*.ckpt"))) == SPLIT.partitions
    with Cluster("local", workers=SPLIT.partitions) as cluster:
        restored = cluster.restore(tmp_path)
        restored.run_for(STEPS)
        assert restored.collect().equals(reference.rows)
        assert restored.states() == reference.states


def test_restore_refuses_a_changed_file(tmp_path):
    """A partition file that no longer matches its digest is refused."""
    with Cluster("local") as cluster:
        cluster.build(GridEpidemic, _scenario(), SPLIT).checkpoint(tmp_path)
    part = tmp_path / "part-00001.ckpt"
    part.write_bytes(part.read_bytes() + b"x")
    with Cluster("local") as cluster, pytest.raises(CheckpointError, match="digest"):
        cluster.restore(tmp_path)


def test_restore_refuses_a_missing_index(tmp_path):
    """A directory without index.json is not a split-run checkpoint."""
    with pytest.raises(CheckpointError, match=r"index\.json"):
        Cluster("local").restore(tmp_path)


def test_workers_must_match_partitions():
    """One worker runs one partition."""
    with pytest.raises(ValueError, match="one worker"):
        Cluster("local", workers=3).build(GridEpidemic, _scenario(), SPLIT)


def test_unknown_backend_and_early_collect_are_refused():
    """An unknown backend name, and collect() before any build, raise."""
    with pytest.raises(ValueError, match="unknown backend"):
        Cluster("carrier-pigeon").build(GridEpidemic, _scenario(), SPLIT)
    with pytest.raises(RuntimeError, match="build or restore"):
        Cluster().collect()


def test_build_does_not_consume_the_scenario():
    """Building from a scenario leaves it ready for a single-process run."""
    scenario = _scenario()
    with Cluster("local") as cluster:
        cluster.build(GridEpidemic, scenario, SPLIT).run_for(STEPS)
    assert single_process(GridEpidemic, scenario, 0).rows.equals(
        single_process(GridEpidemic, _scenario(), 0).rows
    )
    assert Cluster().is_root


def test_dask_backend_matches_one_process():
    """Two Dask actors give the single-process outputs (network model)."""
    pytest.importorskip("distributed")
    scenario = NetworkScenario(rng=5, people=200)
    reference = single_process(NetworkSIR, scenario, STEPS)
    with Cluster("dask", workers=2) as cluster:
        model = cluster.build(NetworkSIR, scenario, partition.graph(2))
        model.run_for(STEPS)
        assert model.collect().equals(reference.rows)
        assert model.states() == reference.states


@pytest.mark.skipif(importlib.util.find_spec("ray") is not None, reason="Ray present")
def test_ray_backend_names_its_extra_when_missing():
    """Without Ray the backend says what to install; Ray is imported lazily."""
    with pytest.raises(ImportError, match=r"modelly-abm\[ray\]"):
        Cluster("ray").build(GridEpidemic, _scenario(), SPLIT)


@pytest.mark.skipif(
    importlib.util.find_spec("ray") is None, reason="Ray is not installed"
)
def test_ray_backend_matches_one_process():
    """Two Ray actors give the single-process outputs (grid model)."""
    reference = single_process(GridEpidemic, _scenario(), STEPS)
    with Cluster("ray", workers=2, num_cpus=2) as cluster:
        model = cluster.build(GridEpidemic, _scenario(), partition.grid_blocks(1, 2))
        model.run_for(STEPS)
        assert model.collect().equals(reference.rows)
