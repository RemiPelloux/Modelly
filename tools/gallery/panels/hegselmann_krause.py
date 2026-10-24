"""Gallery panel: final opinions against the confidence bound."""

import numpy as np

from modelly.zoo.hegselmann_krause.model import HegselmannKrause, HKScenario

BOUNDS = np.linspace(0.02, 0.3, 29)


def draw(ax):
    """Where the opinions settle, for each confidence bound."""
    for epsilon in BOUNDS:
        model = HegselmannKrause(HKScenario(rng=1, epsilon=float(epsilon)))
        model.run()
        x = model.voters.opinion
        ax.scatter(np.full(x.shape[0], epsilon), x, s=2, color="tab:blue", alpha=0.2)
    ax.set_xlabel("confidence bound epsilon")
    ax.set_ylabel("final opinion")
