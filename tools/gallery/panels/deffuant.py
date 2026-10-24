"""Gallery panel: opinion trajectories freezing into clusters."""

import numpy as np

from modelly.zoo.deffuant.model import Deffuant, DeffuantScenario

SHOWN = 60  # trajectories drawn
EPSILON = 0.15


def draw(ax):
    """Opinions of a sample of agents over the sweeps."""
    model = Deffuant(DeffuantScenario(rng=1, epsilon=EPSILON, steps=60))
    history = [model.voters.opinion[:SHOWN].copy()]
    for _ in range(model.scenario.steps):
        model.step()
        history.append(model.voters.opinion[:SHOWN].copy())
    ax.plot(np.array(history), color="tab:blue", alpha=0.3, linewidth=0.8)
    ax.set_xlabel("sweep")
    ax.set_ylabel(f"opinion (epsilon = {EPSILON})")
