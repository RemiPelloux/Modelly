"""modelly.bindings, what the R and Julia packages call: plain values in, data frames out."""

from pathlib import Path

import pytest

from modelly import bindings

TARGET = (
    str(Path(__file__).resolve().parents[1] / "r/modelly/inst/tutorial/epidemic.py")
    + ":Epidemic"
)


def test_parameters_and_a_run_with_r_numbers():
    """R passes 1000 as a float: an int field gets an int; the run conserves people."""
    assert list(bindings.parameters(TARGET)["name"]) == [
        "beta",
        "gamma",
        "population",
        "initial",
    ]
    run = bindings.simulate(
        TARGET, {"population": 1000.0, "beta": 0.4}, seed=99.0, steps=40.0
    )
    assert len(run) == 41 and list(run.columns[:2]) == ["step", "susceptible"]
    assert (run[["susceptible", "infected", "recovered"]].sum(axis=1) == 1000).all()
    model = bindings.model(
        TARGET, [], seed=1
    )  # an empty R list arrives as a Python list
    model.step()
    assert model.susceptible + model.infected + model.recovered == 1000


def test_the_calibration_tutorial_gives_the_documented_posterior():
    """The same numbers as docs/calibration.md, from plain priors and an observed list."""
    cases = bindings.simulate(TARGET, {"beta": 0.4, "gamma": 0.1}, seed=99, steps=40)
    result = bindings.calibrate(
        TARGET, {"beta": ["uniform", 0.05, 1], "gamma": ["uniform", 0.02, 0.5]},
        {"infected": cases["infected"].tolist()[1:]}, steps=40, particles=100, generations=6,
        seed=2027,
    )  # fmt: skip
    summary = result["summary"].set_index("parameter")
    assert round(summary.loc["beta", "mean"], 3) == 0.423
    assert round(summary.loc["gamma", "mean"], 3) == 0.098
    assert set(result) == {"summary", "particles", "trace"}


def test_a_bad_prior_is_refused():
    """Only the four kinds by name."""
    with pytest.raises(ValueError, match="prior"):
        bindings.prior(["cauchy", 0, 1])


def test_a_column_is_the_agents_array_not_a_copy():
    """Writing to the array writes the agent's value; an unknown class is named."""
    model = bindings.model(
        "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
    )
    wealth = bindings.column(model, "MoneyAgent", "wealth")
    wealth[0] = 99
    assert next(iter(model.agents)).wealth == 99 and not wealth.flags["OWNDATA"]
    with pytest.raises(KeyError, match="Nobody"):
        bindings.column(model, "Nobody", "wealth")
