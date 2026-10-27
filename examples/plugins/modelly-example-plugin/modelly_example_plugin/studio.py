"""A Studio tab: the scenario of the model shown, one row per parameter."""

from __future__ import annotations

import pandas as pd
import solara


def scenario_table(model) -> pd.DataFrame:
    """The model's scenario as a two-column table, sorted by parameter."""
    values = dict(model.scenario)
    return pd.DataFrame(
        {"parameter": sorted(values), "value": [str(values[k]) for k in sorted(values)]}
    )


@solara.component
def ScenarioView(state):
    """The parameters of the model the timeline shows."""
    state.revision.get()
    session = state.session
    with session.lock:
        table = scenario_table(session.shown)
    with solara.Card("Scenario"):
        solara.DataFrame(table, items_per_page=len(table) or 1)
