"""Gallery panel: stationary wealth histogram against the exact law."""

import numpy as np

from modelly.zoo.kinetic_wealth.model import KineticScenario, KineticWealth

BURN_IN = 500
SNAPSHOTS = 20
SPACING = 25
SHOWN = 30  # wealth levels drawn


def draw(ax):
    """Pooled histogram of wealth after burn-in, and the exact marginal."""
    model = KineticWealth(KineticScenario(rng=1))
    model.run(BURN_IN)
    counts = np.zeros(SHOWN)
    for _ in range(SNAPSHOTS):
        model.run(SPACING)
        counts += np.bincount(model.wealth, minlength=SHOWN)[:SHOWN]
    levels = np.arange(SHOWN)
    ax.bar(levels, counts / (SNAPSHOTS * model.scenario.n), label="simulated")
    ax.plot(levels, model.stationary_distribution()[:SHOWN], "k.-", label="exact")
    ax.set_yscale("log")
    ax.set_xlabel("wealth")
    ax.set_ylabel("share of agents")
    ax.legend(frameon=False)
