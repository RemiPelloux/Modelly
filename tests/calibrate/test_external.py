"""Bayesian optimisation through an outside library: a fake backend and optuna.

The fake backend is a seeded random search with the same ask/tell interface, so
the adapter's contract (points in the unit box, one tell per ask, best point
returned, same seed same search, checkpoints) is tested without optuna. The
optuna test runs only where optuna is installed (``modelly-abm[calibrate]``).
"""

import importlib.util

import numpy as np
import pytest

from modelly.calibrate import Calibration, ExternalBayesOpt, Prior, Target
from modelly.calibrate.external import OptunaBackend
from tests.calibrate.models import Noisy

pytest.importorskip("pyarrow")

STEPS = 20
TRUE_MEAN = 1.5
EVALUATIONS = 16
TOLERANCE = 0.4


class RandomSearch:
    """A seeded random search: the fake outside optimiser."""

    def __init__(self, dimensions, seed, *, log=None):
        """Draw points from a generator of ``seed``; record every call in ``log``."""
        self.rng = np.random.default_rng(seed)
        self.dimensions = dimensions
        self.log = [] if log is None else log
        self.asked = None

    def ask(self):
        """A uniform point of the unit cube."""
        self.asked = self.rng.random(self.dimensions)
        self.log.append(("ask", tuple(self.asked)))
        return self.asked

    def tell(self, unit, value):
        """Check the point is the one asked, and log the value."""
        assert np.allclose(unit, self.asked)
        self.log.append(("tell", float(value)))


def search(backend, seed=1, **options):
    """The adapter fitting the Noisy model's mean."""
    targets = [Target("value", [TRUE_MEAN], summary=np.mean)]
    priors = {"mean": Prior.uniform(-3.0, 3.0)}
    return ExternalBayesOpt(
        Noisy, priors, targets, steps=STEPS, replicates=2, seed=seed,
        backend=backend, **options,
    )  # fmt: skip


def test_the_adapter_asks_tells_and_returns_the_best_point():
    """One tell per ask, the told value the recorded objective, the best one returned."""
    log = []
    fit = search(RandomSearch, backend_options={"log": log})
    posterior = fit.run(evaluations=EVALUATIONS)
    assert [kind for kind, _ in log] == ["ask", "tell"] * EVALUATIONS
    told = [value for kind, value in log if kind == "tell"]
    assert told == fit.trace()["objective"].tolist()
    assert posterior.info["objective"] == min(told)
    assert posterior.best["mean"] == pytest.approx(TRUE_MEAN, abs=TOLERANCE)


def test_same_seed_same_search_and_a_saved_search_resumes(tmp_path):
    """The search is reproducible for a seed, and survives save and load."""
    first = search(RandomSearch).run(evaluations=6).best
    assert search(RandomSearch).run(evaluations=6).best == first
    fit = search(RandomSearch)
    fit.save(tmp_path / "search.ckpt")
    assert Calibration.load(tmp_path / "search.ckpt").run(evaluations=6).best == first


def test_unknown_backends_and_empty_runs_are_refused():
    """A backend name must be known; a run needs one evaluation at least."""
    with pytest.raises(ValueError, match="backend"):
        search("no-such-library")
    with pytest.raises(ValueError, match="evaluation"):
        search(RandomSearch).run(evaluations=0)


def test_without_optuna_the_error_names_the_extra():
    """The default backend imports optuna only when the search starts."""
    fit = search("optuna")  # no import yet
    if importlib.util.find_spec("optuna") is not None:
        pytest.skip("optuna is installed")
    with pytest.raises(ImportError, match=r"modelly-abm\[calibrate\]"):
        fit.run(evaluations=1)


def test_optuna_finds_the_mean():
    """The seeded TPE sampler of optuna gets close to the true mean, reproducibly."""
    pytest.importorskip("optuna")
    fit = search("optuna")
    posterior = fit.run(evaluations=EVALUATIONS)
    assert posterior.best["mean"] == pytest.approx(TRUE_MEAN, abs=TOLERANCE)
    assert search("optuna").run(evaluations=EVALUATIONS).best == posterior.best
    assert isinstance(fit.optimiser(), OptunaBackend)
