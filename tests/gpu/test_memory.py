"""The memory planner: batches sized to a budget, and batched runs equal to one batch."""

import numpy as np
import pytest

from modelly.gpu import PhiloxStream, plan_memory, run_batched

SEED = 4
ROWS = 10_001


def test_plan_sizes_batches_to_the_budget():
    """batch_rows fit the budget; the slices cover every row once, in order."""
    plan = plan_memory(ROWS, bytes_per_row=16, budget=16 * 3000)
    assert plan.batch_rows == 3000 and plan.batches == 4
    slices = list(plan.slices())
    assert slices[0] == slice(0, 3000) and slices[-1] == slice(9000, ROWS)
    assert plan_memory(ROWS, 8).batches >= 1
    assert plan_memory(10, 8, budget=1).batch_rows == 1
    with pytest.raises(ValueError):
        plan_memory(ROWS, 0)


def recovery_phase(backend, draw):
    """A per-row phase drawing by position: recover with probability 0.3 after day 2."""

    def phase(batch, start):
        xp = backend.xp
        u = draw.random(int(batch["days"].shape[0]), start=start)
        recovers = (batch["days"] > 2) & (u < 0.3)
        return {"state": xp.where(recovers, 2, batch["state"]), "u": u}

    return phase


@pytest.mark.parametrize("budget_rows", [ROWS, 2_500, 999])
def test_batched_run_equals_one_batch(budget_rows):
    """Whatever the batch size, the outputs are those of the run in one batch."""
    rng = np.random.default_rng(0)
    columns = {"state": rng.integers(0, 2, ROWS), "days": rng.integers(0, 6, ROWS)}
    stream = PhiloxStream(SEED)
    draw = stream.draws()
    whole = run_batched(
        plan_memory(ROWS, 8, budget=8 * ROWS),
        recovery_phase(stream.backend, draw),
        columns,
    )
    plan = plan_memory(ROWS, 8, budget=8 * budget_rows)
    batched = run_batched(plan, recovery_phase(stream.backend, draw), columns)
    assert np.array_equal(whole["u"], draw.random(ROWS))
    assert np.array_equal(batched["state"], whole["state"])


def test_gpu_batches_equal_numpy(other_backend):
    """Batches on the GPU backend give numpy's single-batch outputs."""
    rng = np.random.default_rng(1)
    columns = {"state": rng.integers(0, 2, ROWS), "days": rng.integers(0, 6, ROWS)}
    expected = run_batched(
        plan_memory(ROWS, 8, budget=8 * ROWS),
        recovery_phase(PhiloxStream(SEED).backend, PhiloxStream(SEED).draws()),
        columns,
    )
    stream = PhiloxStream(SEED, 0, other_backend)
    plan = plan_memory(ROWS, 8, other_backend, budget=8 * 1_234)
    got = run_batched(
        plan, recovery_phase(other_backend, stream.draws()), columns, other_backend
    )
    assert np.array_equal(got["state"], expected["state"])
