"""Decisions: paired comparisons, cost-effectiveness, robustness and optimisation."""

import numpy as np
import pandas as pd
import pytest

from modelly.decide import (
    Comparison,
    Strategy,
    compare,
    cost_effectiveness,
    interval,
    net_benefit,
    optimise,
    robust,
    sample_futures,
)
from modelly.decide.compare import replicate_seeds
from modelly.decide.vaccination import vaccination_study


def noisy(params, seed):
    """An outcome with a strategy effect and a chance event shared by every strategy."""
    shock = np.random.default_rng(seed).normal(0.0, 10.0)
    effect = params.get("effect", 0.0)
    return {"cases": 100.0 + shock - effect, "effect": effect}


def test_common_random_numbers_pair_the_strategies():
    """Same seed per replicate for every strategy; the paired difference is exact here."""
    study = compare(
        noisy, [Strategy("none"), Strategy("half", {"effect": 5.0})], replicates=30
    )
    seeds = study.runs.pivot(index="replicate", columns="strategy", values="seed")
    assert (seeds["none"] == seeds["half"]).all()
    diff = study.difference("cases").loc["half"]
    assert diff["mean"] == pytest.approx(-5.0) and diff["high"] - diff["low"] < 1e-9
    single = study.summary("cases").loc["half"]
    assert single["high"] - single["low"] > 4  # the chance event, cancelled by pairing


def test_the_vaccination_study_ranks_reproducibly_with_intervals_and_costs():
    """Seniors avert the most deaths, children cost least; a rerun gives the same tables."""
    first, again = vaccination_study(replicates=8), vaccination_study(replicates=8)
    ranking = first.rank("deaths")
    pd.testing.assert_frame_equal(ranking, again.rank("deaths"))
    assert list(ranking.index) == ["seniors", "adults", "children", "nobody"]
    assert ranking.loc["seniors", "high"] < ranking.loc["adults", "low"]
    table = cost_effectiveness(first, "deaths_averted")
    assert table.loc["nobody", "status"] == "dominated"
    assert (
        table.loc["seniors", "status"] == "frontier"
        and table.loc["seniors", "icer"] > 0
    )
    assert net_benefit(first, "deaths_averted", 100_000).index[0] == "seniors"


def synthetic(costs, effects):
    """A comparison with fixed costs and effects, two replicates each."""
    rows = [{"strategy": n, "replicate": r, "seed": r, "cost": c, "effect": e}
            for n, c, e in zip("ABCDE", costs, effects) for r in range(2)]  # fmt: skip
    return Comparison(
        pd.DataFrame(rows), tuple(Strategy(n) for n in "ABCDE"[: len(costs)])
    )


def test_cost_effectiveness_removes_dominance_and_gives_icers():
    """B is dominated by C; D is extendedly dominated by a mix of C and E."""
    table = cost_effectiveness(
        synthetic([0, 50, 40, 70, 100], [0, 5, 10, 12, 20]), "effect"
    )
    assert table["status"].to_dict() == {
        "A": "frontier", "C": "frontier", "B": "dominated",
        "D": "extendedly dominated", "E": "frontier",
    }  # fmt: skip
    assert table.loc["C", "icer"] == pytest.approx(4.0)
    assert table.loc["E", "icer"] == pytest.approx(6.0)


def test_robust_ranks_by_largest_regret():
    """The cautious strategy is never best but never far off; it wins on minimax regret."""

    def run(params, seed):
        return {"loss": abs(params["bet"] - params["world"])}

    strategies = [Strategy("low", {"bet": 0.0}), Strategy("middle", {"bet": 0.5}),
                  Strategy("high", {"bet": 1.0})]  # fmt: skip
    futures = [{"world": w} for w in (0.0, 0.3, 0.7, 1.0)]
    result = robust(run, strategies, futures, "loss", replicates=1, threshold=0.5)
    summary = result.summary()
    assert summary.index[0] == "middle" and summary.loc["middle", "max_regret"] == 0.5
    assert summary.loc["middle", "satisficing"] == 1.0
    assert result.regret().min(axis=0).eq(0).all()


def test_futures_are_a_latin_hypercube_from_a_seed():
    """Inside the ranges, one point per stratum of each, the same for the same seed."""
    futures = sample_futures(
        {"beta": (0.02, 0.05), "compliance": (0.0, 1.0)}, 10, seed=3
    )
    assert futures == sample_futures(
        {"beta": (0.02, 0.05), "compliance": (0.0, 1.0)}, 10, seed=3
    )
    strata = sorted(int(f["compliance"] * 10) for f in futures)
    assert strata == list(range(10))
    assert all(0.02 <= f["beta"] <= 0.05 for f in futures)


def test_optimise_finds_the_best_policy_reproducibly():
    """The minimum of a noisy bowl at 0.3, found twice the same way."""
    pytest.importorskip("optuna")

    def run(params, seed):
        noise = np.random.default_rng(seed).normal(0.0, 0.01)
        return {"loss": (params["coverage"] - 0.3) ** 2 + noise}

    found = optimise(
        run, {"coverage": (0.0, 1.0)}, lambda out: out["loss"], trials=40, seed=2
    )
    again = optimise(
        run, {"coverage": (0.0, 1.0)}, lambda out: out["loss"], trials=40, seed=2
    )
    assert found.params == again.params
    assert found.params["coverage"] == pytest.approx(0.3, abs=0.05)
    assert len(found.trials) == 40


def test_intervals_and_refusals():
    """A Student-t interval; bad comparisons are refused."""
    mean, low, high = interval(np.array([1.0, 2.0, 3.0]))
    assert (mean, round(low, 3), round(high, 3)) == (2.0, -0.484, 4.484)
    assert replicate_seeds(1, 3) == replicate_seeds(1, 3)
    with pytest.raises(ValueError, match="distinct"):
        compare(noisy, [Strategy("a"), Strategy("a")])
    with pytest.raises(ValueError, match="two replicates"):
        compare(noisy, [Strategy("a")], replicates=1)
