"""Gallery panel: Gini over time for three noise-to-exchange ratios."""

import numpy as np
from scipy import integrate, stats

from modelly.zoo.bouchaud_mezard.model import BouchaudMezard, BouchaudMezardScenario

RATIOS = (0.5, 1.0, 1.5)  # sigma^2 / J
N_AGENTS = 1000


def inverse_gamma_gini(shape):
    """Gini of the inverse-gamma law of mean one."""
    law = stats.invgamma(shape, scale=shape - 1)
    area, _ = integrate.quad(lambda x: law.sf(x) ** 2, 0, np.inf, limit=200)
    return 1.0 - area


def draw(ax):
    """Simulated Gini per step, with the stationary prediction dashed."""
    for ratio in RATIOS:
        scenario = BouchaudMezardScenario(rng=1, n=N_AGENTS, volatility=np.sqrt(ratio))
        model = BouchaudMezard(scenario)
        model.run()
        ginis = model.datacollector.get_model_vars_dataframe()["gini"]
        (line,) = ax.plot(
            ginis.index * scenario.dt, ginis, label=f"sigma^2/J = {ratio}"
        )
        expected = inverse_gamma_gini(model.stationary_shape())
        ax.axhline(expected, color=line.get_color(), linestyle="--")
    ax.set_xlabel("time")
    ax.set_ylabel("Gini")
    ax.legend(frameon=False)
