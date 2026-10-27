"""Every bundled example's collected data writes to Parquet and reads back unchanged."""

import importlib
import re
from pathlib import Path

import pytest

from modelly.data.collector import DataCollector
from modelly.data.io import tables_of, write_parquet_atomic

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

STEPS = 3
# (module, model class, optional packages it needs) for every model under modelly/examples.
EXAMPLES = [
    ("advanced.alliance_formation.model", "MultiLevelAllianceModel", ()),
    ("advanced.epstein_civil_violence.model", "EpsteinCivilViolence", ()),
    ("advanced.pd_grid.model", "PdGrid", ()),
    ("advanced.sugarscape_g1mt.model", "SugarscapeG1mt", ()),
    ("advanced.wolf_sheep.model", "WolfSheep", ()),
    ("basic.boid_flockers.model", "BoidFlockers", ()),
    ("basic.boltzmann_wealth_model.model", "BoltzmannWealth", ()),
    ("basic.conways_game_of_life.model", "ConwaysGameOfLife", ()),
    ("basic.schelling.model", "Schelling", ()),
    ("basic.virus_on_network.model", "VirusOnNetwork", ("networkx",)),
    ("behaviour.tram_model.model", "TransitSystem", ()),
    ("llm.llm_opinions.model", "LLMOpinions", ()),
    ("spatial.commuting_city.model", "CommutingCity", ("geopandas", "networkx")),
    ("spatial.layered_epidemic.model", "LayeredEpidemic", ()),
]
# Examples with no tabular data: Boids and Life collect nothing, and the alliance model's
# collector holds only its networkx graph and is not called in step. The test records one
# model reporter for each instead, so their runs write Parquet too.
UNCOLLECTED = {"BoidFlockers", "ConwaysGameOfLife", "MultiLevelAllianceModel"}
MODEL_CLASS = re.compile(r"^class (\w+)\((?:modelly\.)?Model\):", re.MULTILINE)


def build(module: str, name: str, needs: tuple[str, ...]):
    """The example model with its default, seeded scenario."""
    for package in needs:
        pytest.importorskip(package)
    return getattr(importlib.import_module(f"modelly.examples.{module}"), name)()


def collected_tables(model, extra: DataCollector | None) -> dict[str, object]:
    """Every collection of the model's DataCollectors and recorders, as Arrow tables."""
    tables = {}
    collectors = [v for v in vars(model).values() if isinstance(v, DataCollector)]
    if extra is not None:
        collectors = [extra]
    for index, collector in enumerate(collectors):
        for name, table in tables_of(collector).items():
            tables[f"collector{index}_{name}"] = table
    recorders = [v for v in vars(model).values() if hasattr(v, "get_all_dataframes")]
    for recorder in recorders:
        for name, frame in recorder.get_all_dataframes().items():
            tables[f"recorder_{name}"] = pa.Table.from_pandas(
                frame, preserve_index=False
            )
    return tables


@pytest.mark.parametrize(
    ("module", "name", "needs"), EXAMPLES, ids=[name for _, name, _ in EXAMPLES]
)
def test_example_data_round_trips_through_parquet(tmp_path, module, name, needs):
    """Run a few steps, write each collection to Parquet, read it back: the same table."""
    model = build(module, name, needs)
    extra = None
    if name in UNCOLLECTED:
        extra = DataCollector(model_reporters={"agents": lambda m: len(m.agents)})
        extra.collect(model)
    for _ in range(STEPS):
        model.step()
        if extra is not None:
            extra.collect(model)
    tables = collected_tables(model, extra)
    assert any(table.num_rows for table in tables.values()), f"{name} collected nothing"
    for (
        table_name,
        table,
    ) in tables.items():  # a recorder may not have started yet: empty
        path = write_parquet_atomic(table, tmp_path / f"{table_name}.parquet")
        back = pq.read_table(path)
        assert back.equals(table), f"{name}: {table_name} changed through Parquet"


def test_every_example_model_is_listed():
    """A new example model is added to EXAMPLES, so its data is checked too."""
    root = Path(importlib.import_module("modelly.examples").__file__).parent
    defined = {
        match
        for path in root.rglob("*.py")
        for match in MODEL_CLASS.findall(path.read_text(encoding="utf-8"))
    }
    assert defined == {name for _, name, _ in EXAMPLES}
