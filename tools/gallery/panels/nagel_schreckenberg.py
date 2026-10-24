"""Gallery panel: the fundamental diagram, with and without dawdling."""

import numpy as np

from modelly.zoo.nagel_schreckenberg.model import fundamental_diagram

DENSITIES = np.linspace(0.02, 0.9, 24)
TRANSIENT = 200
MEASURED = 100
DAWDLES = (0.0, 0.25, 0.5)


def draw(ax):
    """Flow against density for three dawdling probabilities."""
    for dawdle in DAWDLES:
        flows = fundamental_diagram(
            DENSITIES, TRANSIENT, MEASURED, rng=1, dawdle=dawdle
        )
        ax.plot(DENSITIES, flows, marker=".", label=f"dawdle {dawdle}")
    ax.set_xlabel("density (cars per cell)")
    ax.set_ylabel("flow (cars per step)")
    ax.legend(frameon=False)
