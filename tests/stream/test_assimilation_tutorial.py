"""The nowcasting tutorial (docs/assimilation.md) runs and its claims hold."""

import re
import sys
import types
from pathlib import Path

import pytest

TUTORIAL = Path(__file__).resolve().parents[2] / "docs" / "assimilation.md"
BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
NOT_RUN = "# Not run here"
MODULE = "assimilation_tutorial"
TRUE_BETA = 0.45
BETA_TOLERANCE = 0.05
# The filtered nowcast error must be at most this share of the free ensemble's.
TRACKING_RATIO = 0.2


def _code() -> str:
    """Every Python block of the tutorial that runs without a broker, in order."""
    blocks = BLOCK.findall(TUTORIAL.read_text(encoding="utf-8"))
    return "\n".join(b for b in blocks if not b.startswith(NOT_RUN))


@pytest.fixture(scope="module")
def tutorial():
    """The tutorial's namespace after running it as an importable module.

    The module is registered in ``sys.modules`` so its model classes pickle,
    as they do in a script or a notebook.
    """
    module = types.ModuleType(MODULE)
    sys.modules[MODULE] = module
    try:
        code = compile(_code(), str(TUTORIAL), "exec")
        exec(code, module.__dict__)  # noqa: S102 - the repository's own tutorial
        yield module
    finally:
        del sys.modules[MODULE]


def test_the_particle_filter_tracks_the_truth(tutorial):
    """The filtered nowcast of the hidden prevalence beats the free ensemble by far."""
    assert tutorial.rmse_filtered < TRACKING_RATIO * tutorial.rmse_free
    assert tutorial.pf.resamplings > 0
    assert len(tutorial.pf.history) == tutorial.DAYS


def test_the_ensemble_kalman_filter_recovers_the_contact_rate(tutorial):
    """The EnKF's ensemble mean of beta ends near the truth's 0.45."""
    assert tutorial.beta_estimate == pytest.approx(TRUE_BETA, abs=BETA_TOLERANCE)


def test_the_bands_are_plain_frames(tutorial):
    """Now and ahead, one row per time with the requested quantile columns."""
    assert list(tutorial.now["time"]) == [float(tutorial.DAYS)]
    ahead = tutorial.ahead
    assert ahead["time"].tolist() == [float(t) for t in range(50, 65)]
    assert list(ahead.columns[-5:]) == ["q0.05", "q0.25", "q0.5", "q0.75", "q0.95"]
    assert (ahead["q0.05"] <= ahead["q0.95"]).all()
    assert tutorial.filtered.time == tutorial.DAYS  # the forecast ran copies
