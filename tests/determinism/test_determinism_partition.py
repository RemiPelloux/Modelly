"""Split runs are the same run: the partition-independence part of the suite.

The reference models of split runs (``modelly.examples.distributed``) are golden
examples, so their single-process run is compared with ``golden.json`` on every
platform and build. Here each one also runs from the golden seed split into
several partitions on the local backend, and every reporter row and every agent's
state (attributes, location, random streams) must equal the single-process run,
byte for byte. Together: a split run on any platform gives the golden run. MPI
ranks are checked by ``tests/distributed/test_mpi.py`` where ``mpirun`` exists.
"""

import pytest

from modelly.dev.golden import EXAMPLES_BY_NAME, SEED, _resolve
from modelly.distributed import check_independence, partition

# How each reference model is split: grid blocks, graph parts, k-d boxes.
SPLITS = {
    "grid_epidemic": lambda: [
        partition.grid_blocks(1, 1),
        partition.grid_blocks(2, 1),
        partition.grid_blocks(2, 2),
        partition.grid_blocks(4, 4),
    ],
    "network_sir": lambda: [partition.graph(k) for k in (2, 4, 16)],
    "continuous_sir": lambda: [partition.kd(k) for k in (2, 4, 16)],
}
REFERENCE_PACKAGE = "distributed."


@pytest.mark.parametrize("name", sorted(SPLITS))
def test_split_runs_equal_the_golden_run(name):
    """Every split of the reference model gives its single-process outputs."""
    example = EXAMPLES_BY_NAME[name]
    if not example.available():
        pytest.skip(f"{name} needs {', '.join(example.requires)}")
    scenario = _resolve(example.scenario)(rng=SEED)
    run = check_independence(
        _resolve(example.model), scenario, SPLITS[name](), example.steps
    )
    assert len(run.rows) == example.steps + 1


def test_every_reference_model_is_split():
    """A new reference model of split runs joins this suite as well."""
    examples = EXAMPLES_BY_NAME.values()
    split = {e.name for e in examples if e.model.startswith(REFERENCE_PACKAGE)}
    assert split == set(SPLITS)
