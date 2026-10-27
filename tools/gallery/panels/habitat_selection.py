"""Gallery panel: share of the animals per land-cover class, converging to the law."""

from modelly.space.geo.samples import WORLDCOVER_CLASSES
from modelly.zoo.habitat_selection.model import HabitatScenario, HabitatSelection

SEED = 1
SHOWN = (10, 30, 40)  # tree cover, grassland, cropland


def draw(ax):
    """Class shares over time from a uniform start, with the stationary shares dashed."""
    model = HabitatSelection(HabitatScenario(rng=SEED, steps=150))
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    law = dict(zip(model.classes.tolist(), model.stationary_shares()))
    for value in SHOWN:
        line = ax.plot(frame[f"class_{value}"], label=WORLDCOVER_CLASSES[value])[0]
        ax.axhline(law[value], linestyle="--", color=line.get_color())
    ax.set_xlabel("step")
    ax.set_ylabel("share of the animals")
    ax.legend(frameon=False)
