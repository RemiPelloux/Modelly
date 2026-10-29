"""The experiment browser: a results store's runs, filtered, one output against a parameter."""

import pytest

from modelly.experiments import Experiment, ScenarioSpace, designs
from modelly.studio.browser import ExperimentBrowser
from tests.experiments.models import Walk

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")

STEPS = 4
REPLICATES = 2
POINTS = 6


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    """A finished sweep of the Walk model over drift and policy."""
    return sweep(tmp_path_factory.mktemp("store"))


def sweep(path):
    """Run the Walk sweep into the store folder ``path``; the folder."""
    space = ScenarioSpace(drift=(0.0, 1.0), policy=["a", "b"], n=5)
    Experiment(
        Walk,
        space,
        design=designs.latin_hypercube(POINTS),
        replicates=REPLICATES,
        steps=STEPS,
        outputs=["mean", "spread"],
        store=path,
        seed=3,
    ).run("serial")
    return path


def test_one_row_per_run(store):
    """Every run once, at its last step; the parameters and outputs are named."""
    browser = ExperimentBrowser(store)
    runs = browser.runs()
    assert len(runs) == POINTS * REPLICATES
    assert set(runs["step"]) == {STEPS}
    assert runs["run_id"].is_unique
    assert set(browser.parameters) == {"drift", "policy", "n"}  # n is fixed, still one
    assert browser.outputs == ["mean", "spread"]
    assert "12 run(s)" in browser.describe()


def test_select_by_range_and_by_values(store):
    """A range keeps both ends; a list keeps those values; together they intersect."""
    browser = ExperimentBrowser(store)
    every = browser.runs()
    low = every["drift"].median()
    high_drift = browser.select({"drift": (low, 1.0)})
    assert (high_drift["drift"] >= low).all()
    assert 0 < len(high_drift) < len(every)
    only_a = browser.select({"policy": ["a"]})
    assert set(only_a["policy"]) == {"a"}
    both = browser.select({"drift": (low, 1.0), "policy": ["a"]})
    assert len(both) <= min(len(high_drift), len(only_a))
    assert len(browser.select()) == len(every)
    with pytest.raises(KeyError):
        browser.select({"nothing": ["x"]})


def test_an_output_against_a_parameter(store):
    """One summary row per value of the parameter, with the run count."""
    browser = ExperimentBrowser(store)
    summary = browser.against("policy", "mean")
    assert list(summary.columns) == ["policy", "mean", "min", "max", "count"]
    assert summary["count"].sum() == POINTS * REPLICATES
    assert (summary["min"] <= summary["max"]).all()


def test_runs_step_by_step(store):
    """One column per chosen run, one row per step."""
    browser = ExperimentBrowser(store)
    ids = list(browser.runs()["run_id"])[:3]
    series = browser.series("mean", ids)
    assert list(series.columns) == sorted(ids)
    assert list(series.index) == list(range(STEPS + 1))


def test_an_empty_folder(tmp_path):
    """A folder with no finished run cannot be browsed."""
    with pytest.raises(LookupError):
        ExperimentBrowser(tmp_path)
