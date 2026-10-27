"""Gallery panel: simulated street flows against their expectation from the betweenness."""

import numpy as np

from modelly.zoo.road_traffic.model import RoadTraffic, RoadTrafficScenario

SEED = 1


def draw(ax):
    """Every street segment's flow against ``T B(e) / (n (n - 1))``, with the identity."""
    model = RoadTraffic(RoadTrafficScenario(rng=SEED))
    model.run()
    expected = model.expected_flows()
    ax.scatter(expected, model.flows, s=6, alpha=0.6)
    top = float(np.max([expected.max(), model.flows.max()]))
    ax.plot([0, top], [0, top], linestyle="--", color="grey", label="expectation")
    ax.set_xlabel("expected vehicles per segment")
    ax.set_ylabel("simulated vehicles")
    ax.legend(frameon=False)
