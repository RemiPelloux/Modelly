"""The partition-independence suite: split runs equal one process, byte for byte.

Each reference model of ``modelly.examples.distributed`` runs in one process
(``model.step()`` in a loop) and split into 1, 2, 4 and 16 partitions on the
local backend; the reporter rows and the full state of every agent (attributes,
location and random streams) must be identical.
"""

import pytest

from modelly.distributed import check_independence, partition, single_process
from modelly.examples.distributed.continuous_sir import ContinuousSIR, WalkerScenario
from modelly.examples.distributed.grid_epidemic import EpidemicScenario, GridEpidemic
from modelly.examples.distributed.network_sir import NetworkScenario, NetworkSIR

STEPS = 12
SEEDS = (1, 2)
GRID = {"width": 32, "height": 32, "people": 600, "infected": 10}
NETWORK = {"people": 480, "infected": 6}
WALKERS = {"side": 24.0, "people": 400}


@pytest.mark.parametrize("seed", SEEDS)
def test_grid_epidemic_on_1_2_4_and_16_blocks(seed):
    """Grid blocks of 1, 2, 4 and 16 partitions give the single-process outputs."""
    splits = [
        partition.grid_blocks(1, 1),
        partition.grid_blocks(2, 1),
        partition.grid_blocks(2, 2),
        partition.grid_blocks(4, 4),
    ]
    run = check_independence(
        GridEpidemic, EpidemicScenario(rng=seed, **GRID), splits, STEPS
    )
    assert run.rows["I"].max() > GRID["infected"]  # the epidemic spreads


@pytest.mark.parametrize("seed", SEEDS)
def test_network_sir_on_2_4_and_16_parts(seed):
    """Graph parts of 2, 4 and 16 give the single-process outputs."""
    splits = [partition.graph(2), partition.graph(4), partition.graph(16)]
    run = check_independence(
        NetworkSIR, NetworkScenario(rng=seed, **NETWORK), splits, STEPS
    )
    assert run.rows["R"].iloc[-1] > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_continuous_walkers_on_2_4_and_16_boxes(seed):
    """k-d boxes of 2, 4 and 16 give the single-process outputs."""
    splits = [partition.kd(2), partition.kd(4), partition.kd(16)]
    run = check_independence(
        ContinuousSIR, WalkerScenario(rng=seed, **WALKERS), splits, STEPS
    )
    assert run.rows["I"].max() > 0


def test_agents_really_change_partitions():
    """Walkers cross block borders, so migration is exercised, not just ghosts."""
    from modelly.distributed import Cluster  # noqa: PLC0415

    with Cluster("local") as cluster:
        model = cluster.build(
            GridEpidemic, EpidemicScenario(rng=1, **GRID), partition.grid_blocks(2, 2)
        )
        before = model.snapshot()["location"]
        owners = model.group.workers[0].layout.owners
        model.run_for(STEPS)
        after = model.snapshot()["location"]
    moved = (owners(list(before)) != owners(list(after))).sum()
    assert moved > GRID["people"] // 10


def test_different_seeds_give_different_runs():
    """The suite would not pass trivially: another seed changes the outputs."""
    first = single_process(GridEpidemic, EpidemicScenario(rng=1, **GRID), STEPS)
    second = single_process(GridEpidemic, EpidemicScenario(rng=2, **GRID), STEPS)
    assert not first.rows.equals(second.rows)
