"""The Python side of docs/r_and_julia.md: its snippets, its SQL and the calls R and Julia make.

R and Julia are not run here. Instead the Python snippets run as written, the SQL of the R
and Julia snippets runs through DuckDB's Python package on the files they wrote, and the
calls the reticulate and PythonCall snippets make into Modelly are made from Python.
"""

import importlib
import re
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "r_and_julia.md"
BLOCK = re.compile(r"```(\w+)\n(.*?)```", re.DOTALL)
SQL = re.compile(r'"(SELECT [^"]+)"')
IMPORTED = re.compile(r'(?:import|pyimport)\("([\w.]+)"\)')
STEPS = 20


def blocks(language: str) -> list[str]:
    """The code blocks of the guide in ``language``, in order."""
    text = GUIDE.read_text(encoding="utf-8")
    return [code for lang, code in BLOCK.findall(text) if lang == language]


@pytest.fixture
def written(tmp_path, monkeypatch) -> Path:
    """A folder where the guide's Python snippets have run, in order."""
    monkeypatch.chdir(tmp_path)
    namespace: dict = {}
    for code in blocks("python"):
        if "to_xarray" in code and importlib.util.find_spec("xarray") is None:
            continue  # the netCDF snippet needs the optional xarray extra
        exec(compile(code, str(GUIDE), "exec"), namespace)  # noqa: S102 (our own docs)
    return tmp_path


def test_python_snippets_write_the_files(written):
    """The run, the sweep and the database file the R and Julia snippets read exist."""
    assert (written / "out" / "model.parquet").is_file()
    assert (written / "out" / "agents.parquet").is_file()
    assert len(list((written / "runs" / "boltzmann").glob("run-*.parquet"))) == 8
    assert (written / "results.duckdb").is_file()


@pytest.mark.parametrize("language", ["r", "julia"])
def test_sql_of_the_r_and_julia_snippets(written, language):
    """Every query the R or Julia snippets send to DuckDB runs and returns rows."""
    queries = [query for code in blocks(language) for query in SQL.findall(code)]
    assert queries
    with duckdb.connect(str(written / "results.duckdb"), read_only=True) as con:
        for query in queries:
            assert con.sql(query).fetchall(), query


@pytest.mark.parametrize("language", ["r", "julia"])
def test_modules_the_snippets_import(language):
    """Every Python module the reticulate and PythonCall snippets import exists."""
    names = [name for code in blocks(language) for name in IMPORTED.findall(code)]
    assert names or language == "julia"
    for name in names:
        importlib.import_module(name)


def test_calls_made_from_r_and_julia(tmp_path, monkeypatch):
    """The reticulate and PythonCall snippets' calls, made from Python with the same values."""
    monkeypatch.chdir(tmp_path)
    boltzmann = importlib.import_module(
        "modelly.examples.basic.boltzmann_wealth_model.model"
    )
    scenario = boltzmann.BoltzmannScenario(rng=42, n=100)
    model = boltzmann.BoltzmannWealth(scenario=scenario)
    for _ in range(STEPS):
        model.step()
    gini = model.datacollector.get_model_vars_dataframe()
    assert len(gini) == STEPS + 1 and "Gini" in gini
    model.datacollector.to_parquet("out/from_r.parquet")
    experiments = importlib.import_module("modelly.experiments")
    experiment = experiments.Experiment(
        model=boltzmann.BoltzmannWealth,
        space=experiments.ScenarioSpace(n=(50, 100), width=10, height=10),
        design=experiments.designs.latin_hypercube(4),
        replicates=2,
        steps=10,
        outputs=["gini"],
        store="runs/from_r",
        seed=42,
    )
    assert experiment.run(executor="serial").done == len(experiment.tasks())
    assert (tmp_path / "out" / "from_r.parquet").is_file()


def test_a_double_seed_is_refused():
    """An R double (42 rather than 42L) is not a seed, as the guide warns."""
    boltzmann = importlib.import_module(
        "modelly.examples.basic.boltzmann_wealth_model.model"
    )
    with pytest.raises(TypeError):
        boltzmann.BoltzmannScenario(rng=42.0)
