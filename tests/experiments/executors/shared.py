"""The experiment every executor test runs, so their results can be compared."""

from modelly.experiments import Experiment, ScenarioSpace, designs
from tests.experiments.models import Walk, first_position

MAX_PARALLEL = 2


def experiment(store, outputs=None):
    """A Sobol design of four points, two replicates, five steps, three outputs."""
    return Experiment(
        Walk,
        ScenarioSpace(drift=(0.0, 1.0), policy=["a", "b"], n=6),
        design=designs.sobol(4),
        replicates=2,
        steps=5,
        outputs=outputs
        or {"mean": "mean", "spread": "spread", "first": first_position},
        store=store,
        seed=21,
    )
