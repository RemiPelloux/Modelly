"""Gallery panel: the epidemic curve of each age group."""

from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario, State

GROUPS = ("children", "adults", "seniors")


def draw(ax):
    """Infectious share of each age group over time."""
    model = AgeSEIR(SEIRScenario(rng=1))
    shares = []
    for _ in range(model.scenario.steps):
        model.step()
        shares.append(model.counts()[:, State.I] / model.sizes)
    for k, label in enumerate(GROUPS):
        ax.plot([row[k] for row in shares], label=label)
    ax.set_xlabel("step")
    ax.set_ylabel("share infectious")
    ax.legend(frameon=False)
