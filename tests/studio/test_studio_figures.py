"""The figures of the ensemble, assimilation and experiment views, and the Analysis tab's."""

import numpy as np
import pandas as pd
import pytest

from modelly.sensitivity import morris
from modelly.sensitivity.results import SensitivityResult
from modelly.studio import figures
from modelly.studio.analyses import (
    POSTERIOR,
    SENSITIVITY,
    as_list,
    load_analyses,
    view_of,
)
from tests.calibrate.shared import sir_smc
from tests.sensitivity.models import ishigami
from tests.sensitivity.test_variance import ISHIGAMI

pytest.importorskip("pyarrow")


def bands_frame() -> pd.DataFrame:
    """A two-quantity band over three times."""
    rows = []
    for time in range(3):
        for name, base in (("cases", 10.0), ("deaths", 1.0)):
            rows.append(
                {"time": float(time), "quantity": name, "mean": base + time}
                | {"q0.05": base, "q0.5": base + time, "q0.95": base + 2 * time}
            )
    return pd.DataFrame(rows)


def test_band_levels_and_figure():
    """The quantile columns are read in order; one panel per quantity."""
    bands = bands_frame()
    assert figures.band_levels(bands) == [0.05, 0.5, 0.95]
    observed = pd.DataFrame({"time": [1.0], "quantity": ["cases"], "value": [11.0]})
    figure = figures.band_figure(bands, observed)
    assert len(figure.axes) == 2
    assert figures.band_figure(bands.iloc[0:0]) is None


def test_filter_and_experiment_figures():
    """ESS, weights, trajectories, an output against a parameter and run series."""
    history = pd.DataFrame(
        {"time": [1.0, 2.0], "ess": [7.0, 3.0], "resampled": [False, True]}
    )
    assert figures.ess_figure(history, 8, 0.5).axes
    weights = pd.DataFrame(np.full((2, 4), 0.25), index=[1.0, 2.0])
    assert len(figures.weights_figure(weights).axes) == 2  # the map and its colour bar
    kalman = pd.DataFrame(
        {"time": [1.0, 2.0], "rate": [0.1, 0.2], "rate_sd": [0.05, 0.02]}
    )
    assert len(figures.trajectory_figure(kalman, ["rate"]).axes) == 1
    runs = pd.DataFrame({"x": [1, 1, 2], "y": [0.5, 0.7, 0.9]})
    summary = runs.groupby("x")["y"].agg(["mean"]).reset_index()
    assert figures.against_figure(runs, summary, "x", "y").axes
    series = pd.DataFrame({"r1": [0, 1], "r2": [0, 2]})
    assert len(figures.series_figure(series, "y").axes[0].lines) == 2


def test_posterior_and_sensitivity_views():
    """A posterior shows its pairs and HDI table; a Morris result its ranking."""
    posterior = sir_smc(particles=12).run(generations=1)
    view = view_of("SIR", posterior)
    assert view.kind == POSTERIOR
    assert list(view.table["parameter"]) == ["beta", "gamma"]
    assert {"hdi_low", "hdi_high"} <= set(view.table.columns)
    assert view.figure().axes
    screen = morris(ishigami, ISHIGAMI, trajectories=4)
    view = view_of("Ishigami", screen)
    assert view.kind == SENSITIVITY
    assert view.table["parameter"].iloc[0] == screen.ranking().index[0]
    assert view.figure().axes
    with pytest.raises(TypeError, match="Posterior"):
        view_of("bad", 42)


def test_analyses_from_a_function(tmp_path):
    """``--analysis file.py:function``: one result, a list or a dict, named."""
    table = pd.DataFrame({"mu_star": [1.0]}, index=["x"])
    result = SensitivityResult("custom", table, "mu_star")
    assert as_list(result) == [("result", result)]
    assert as_list([result]) == [("result 1", result)]
    assert as_list({"mine": result}) == [("mine", result)]
    source = tmp_path / "analysis.py"
    source.write_text(
        "import pandas as pd\n"
        "from modelly.sensitivity.results import SensitivityResult\n\n\n"
        "def results():\n"
        "    table = pd.DataFrame({'mu_star': [2.0]}, index=['y'])\n"
        "    return {'screen': SensitivityResult('custom', table, 'mu_star')}\n",
        encoding="utf-8",
    )
    [(name, found)] = load_analyses(f"{source}:results")
    assert name == "screen"
    assert found.method == "custom"
