"""run_batch and run_grid: parallel runs with results in a deterministic order."""

import pandas as pd
import pytest

from modelly import Model, run_batch, run_grid
from modelly.batch import default_workers, grid_tasks


def season(task):
    """A tiny seeded model run: the result depends only on the task's seed."""
    model = Model(rng=task["seed"])
    return {"draws": sum(model.random.randint(0, 9) for _ in range(task["n"]))}


def test_run_batch_preserves_order_and_matches_the_loop():
    """Parallel results equal the sequential loop's, in task order."""
    tasks = [{"seed": s, "n": 50} for s in range(12)]
    expected = [season(t) for t in tasks]
    assert run_batch(season, tasks, workers=1) == expected
    assert run_batch(season, tasks, workers=4) == expected


def test_run_batch_accepts_closures_and_lambdas():
    """Forked workers inherit the function, so it need not be importable."""
    offset = 7
    assert run_batch(lambda x: x + offset, range(10), workers=3) == [
        x + 7 for x in range(10)
    ]


def test_errors_propagate():
    """A failing run raises, as in the sequential loop."""

    def boom(x):
        if x == 3:
            raise ValueError("run 3 failed")
        return x

    with pytest.raises(ValueError, match="run 3 failed"):
        run_batch(boom, range(6), workers=2)


def test_grid_seeds_are_deterministic_and_distinct():
    """The design and its seeds depend on the seed argument only."""
    a = grid_tasks({"n": [1, 2], "beta": [0.1, 0.2, 0.3]}, replicates=3, seed=5)
    b = grid_tasks({"n": [1, 2], "beta": [0.1, 0.2, 0.3]}, replicates=3, seed=5)
    assert a == b and len(a) == 18
    assert len({t["seed"] for t in a}) == 18
    assert a[0] == {"n": 1, "beta": 0.1, "replicate": 0, "seed": a[0]["seed"]}
    assert (
        grid_tasks({"n": [1]}, seed=6)[0]["seed"]
        != grid_tasks({"n": [1]}, seed=5)[0]["seed"]
    )


def test_run_grid_returns_one_row_per_run_whatever_the_workers():
    """Same DataFrame with one worker and with several."""
    grid = {"n": [10, 20]}
    one = run_grid(season, grid, replicates=3, seed=1, workers=1)
    many = run_grid(season, grid, replicates=3, seed=1, workers=3)
    pd.testing.assert_frame_equal(one, many)
    assert list(one.columns) == ["n", "replicate", "seed", "draws"]
    assert len(one) == 6


def test_default_workers_reads_the_environment(monkeypatch):
    """MODELLY_WORKERS overrides the CPU-based default."""
    monkeypatch.setenv("MODELLY_WORKERS", "3")
    assert default_workers() == 3
    monkeypatch.delenv("MODELLY_WORKERS")
    assert 1 <= default_workers() <= 8
