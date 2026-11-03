"""Gallery panel: virus loads of hosts infected at different times, and the share infectious."""

import numpy as np

from modelly.zoo.within_host.model import Host, WithinHost, WithinHostScenario

QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)
FLOOR = 1e-7


def draw(ax):
    """Virus load of five hosts (log scale) whose onsets span the outbreak, and the share."""
    model = WithinHost(WithinHostScenario(rng=1, hosts=5_000, days=40))
    loads = []
    for _ in range(model.scenario.days):
        model.step()
        loads.append(model.columns[Host].virus.copy())
    loads = np.array(loads)
    onset = model.columns[Host].onset
    ranked = np.argsort(np.where(np.isfinite(onset), onset, np.inf))
    count = int(np.isfinite(onset).sum())
    hosts = [ranked[int(q * (count - 1))] for q in QUANTILES]
    days = np.arange(1, model.scenario.days + 1)
    ax.semilogy(days, np.maximum(loads[:, hosts], FLOOR), linewidth=0.8)
    ax.axhline(model.scenario.threshold, color="0.5", linestyle=":", linewidth=0.8)
    ax.set_ylim(FLOOR, 10)
    ax.set_xlabel("day")
    ax.set_ylabel("virus load (dotted: infectious)")
    share = (
        model.datacollector.get_model_vars_dataframe()["infectious"]
        / model.scenario.hosts
    )
    twin = ax.twinx()
    twin.plot(share.index, share, color="black", linewidth=1.2)
    twin.set_ylabel("share infectious (black)")
