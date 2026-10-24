"""Gallery panel: adoption curves, well-mixed and on networks, against the Bass equation."""

from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario, bass_curve

RUNS = (
    ("well-mixed", {"mixing": "well-mixed"}),
    ("network, 50 neighbours", {"mixing": "network", "degree": 50}),
    ("network, 4 neighbours", {"mixing": "network", "degree": 4}),
)
HOUSEHOLDS = 2000


def draw(ax):
    """Share adopted over time for each mixing, and the Bass solution."""
    for label, params in RUNS:
        model = BassDiffusion(BassScenario(rng=1, households=HOUSEHOLDS, **params))
        model.run()
        frame = model.datacollector.get_model_vars_dataframe()
        ax.plot(frame["time"], frame["adoption"], label=label)
    s = model.scenario
    ax.plot(
        frame["time"],
        bass_curve(frame["time"], s.innovation, s.imitation),
        "k--",
        label="Bass equation",
    )
    ax.set_xlabel("years")
    ax.set_ylabel("share adopted")
    ax.legend(frameon=False)
