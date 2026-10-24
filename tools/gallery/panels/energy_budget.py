"""Gallery panel: the population settles at the carrying capacity."""

from modelly.zoo.energy_budget.model import EnergyBudget, EnergyScenario


def draw(ax):
    """Population over time with the carrying capacity from the energy balance."""
    model = EnergyBudget(EnergyScenario(rng=1))
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    ax.plot(frame.index, frame["foragers"], label="foragers")
    ax.axhline(model.carrying_capacity(), linestyle="--", color="grey", label="K")
    ax.set_xlabel("step")
    ax.set_ylabel("population")
    ax.legend(frameon=False)
