"""Gallery panel: number of cultural regions against the number of traits."""

import numpy as np

from modelly.zoo.axelrod.model import Axelrod, AxelrodScenario

TRAITS = (2, 5, 10, 15, 20, 30, 45, 60)
SEEDS = (1, 2, 3)


def draw(ax):
    """Mean number of frozen regions on the 10 x 10 grid, five features."""
    means = []
    for traits in TRAITS:
        regions = []
        for seed in SEEDS:
            model = Axelrod(AxelrodScenario(rng=seed, traits=traits))
            model.run()
            regions.append(model.n_regions())
        means.append(np.mean(regions))
    ax.plot(TRAITS, means, marker="o")
    ax.set_xlabel("traits per feature")
    ax.set_ylabel("cultural regions (of 100 sites)")
