"""Gallery panel: infectious hosts for three vector densities."""

from modelly.zoo.vector_borne.model import VectorBorne, VectorScenario

DENSITIES = (0.5, 2.0, 4.0)


def draw(ax):
    """Share of hosts infectious over time, one line per vector density."""
    for m in DENSITIES:
        model = VectorBorne(VectorScenario(rng=1, m=m))
        model.run()
        frame = model.datacollector.get_model_vars_dataframe()
        hosts = frame.iloc[0].sum()
        label = f"m = {m:g}, R0 = {model.r0():.1f}"
        ax.plot(frame.index, frame["I"] / hosts, label=label)
    ax.set_xlabel("day")
    ax.set_ylabel("share of hosts infectious")
    ax.legend(frameon=False)
