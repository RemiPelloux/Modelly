"""Gallery panel: hospital occupancy and beds, with and without the contact response."""

from modelly.zoo.hospital_epidemic.model import HospitalEpidemic, HospitalScenario

RESPONSES = (0.0, 1.0)


def draw(ax):
    """Occupied beds (solid) and open beds (dashed) over time for two responses."""
    for response in RESPONSES:
        model = HospitalEpidemic(HospitalScenario(rng=1, response=response, steps=150))
        model.run()
        frame = model.datacollector.get_model_vars_dataframe()
        (line,) = ax.plot(
            frame.index, frame["occupied"], label=f"occupied, response {response:g}"
        )
        ax.plot(frame.index, frame["beds"], linestyle="--", color=line.get_color())
    ax.set_xlabel("day")
    ax.set_ylabel("beds (dashed: open)")
    ax.legend(frameon=False)
