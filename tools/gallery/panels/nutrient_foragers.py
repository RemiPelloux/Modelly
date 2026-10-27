"""Gallery panel: foragers and nutrient fall away from the river bank."""

from modelly.zoo.nutrient_foragers.model import NutrientForagers, NutrientScenario


def draw(ax):
    """Mean foragers and nutrient per cell against the distance from the western edge."""
    model = NutrientForagers(NutrientScenario(rng=1))
    model.run()
    ax.plot(model.density_by_column(), label="foragers per cell")
    ax.plot(model.field.values.mean(axis=1), label="nutrient per cell")
    ax.set_xlabel("distance from the river (cells)")
    ax.set_ylabel("per cell")
    ax.legend(frameon=False)
