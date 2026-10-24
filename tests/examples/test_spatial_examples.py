"""The geospatial commuting and layered-epidemic examples run, repeat and checkpoint."""

import gc
import weakref

import pytest

from modelly import Model
from modelly.examples.spatial.layered_epidemic.model import (
    EpidemicScenario,
    LayeredEpidemic,
)


def test_commuting_city(tmp_path):  # noqa: D103
    pytest.importorskip("geopandas")
    from modelly.examples.spatial.commuting_city.model import (  # noqa: PLC0415
        CommutingCity,
        CommutingScenario,
    )

    model = CommutingCity(CommutingScenario(rng=42))
    model.run_for(4)
    frame = model.datacollector.get_model_vars_dataframe()
    assert frame["in_centre"].iloc[0] > frame["in_centre"].iloc[1]
    assert (frame["mean_trip_minutes"] > 0).all()

    model.save(tmp_path / "commuting.ckpt")
    restored = Model.load(tmp_path / "commuting.ckpt")
    model.run_for(2)
    restored.run_for(2)
    assert restored.datacollector.get_model_vars_dataframe().equals(
        model.datacollector.get_model_vars_dataframe()
    )

    again = CommutingCity(CommutingScenario(rng=42))
    again.run_for(6)
    assert again.datacollector.get_model_vars_dataframe().equals(
        model.datacollector.get_model_vars_dataframe()
    )


def test_layered_epidemic(tmp_path):  # noqa: D103
    model = LayeredEpidemic(EpidemicScenario(rng=42))
    assert model.network.layers == ["household", "school", "work"]
    assert model.contacts.shape == (3, 3)
    model.run_for(30)
    frame = model.datacollector.get_model_vars_dataframe()
    assert (frame[["susceptible", "infected", "recovered"]].sum(axis=1) == 352).all()
    assert not model.schools_open
    assert frame["mean_contacts"].iloc[-1] < frame["mean_contacts"].iloc[0]
    assert model.attack_rate_by_group().max() > 0
    assert next(iter(model.agents)).state.name in {
        "SUSCEPTIBLE",
        "INFECTED",
        "RECOVERED",
    }

    model.save(tmp_path / "epidemic.ckpt")
    restored = Model.load(tmp_path / "epidemic.ckpt")
    model.run_for(5)
    restored.run_for(5)
    assert (restored.state == model.state).all()

    ref = weakref.ref(model)
    model.remove_all_agents()
    del model
    gc.collect()
    assert ref() is None
