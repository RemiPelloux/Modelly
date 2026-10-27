"""Gallery panel: dissimilarity between the groups over time, for three thresholds."""

from modelly.zoo.schelling_regions.model import (
    SchellingRegions,
    SchellingRegionsScenario,
)

SEED = 1
THRESHOLDS = (0.3, 0.45, 0.5)
STEPS = 60


def draw(ax):
    """Duncan's dissimilarity index per step on the Chittenden County tracts."""
    for threshold in THRESHOLDS:
        scenario = SchellingRegionsScenario(rng=SEED, threshold=threshold, steps=STEPS)
        model = SchellingRegions(scenario)
        model.run()
        frame = model.datacollector.get_model_vars_dataframe()
        settled = frame["dissimilarity"].reindex(range(STEPS + 1)).ffill()
        ax.plot(settled, label=f"threshold {threshold}")
    ax.set_xlabel("step (a run stops once everybody is happy)")
    ax.set_ylabel("dissimilarity index")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False)
