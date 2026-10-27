"""A run that calls a language model bundles its replies and verifies offline.

The town model below asks every voter a question through ``model.llm``. It is
recorded with a local stand-in provider; for the verification the model builds a
real HTTP provider instead (``TOWN_PROVIDER=http``) pointed at a closed port, with
sockets refused in the process: only the replies packed in the bundle can answer.
"""

import json
import socket
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest

from modelly.llm import CacheMiss, Client, FakeProvider, ProviderError
from modelly.llm.replay import active_replay, replaying
from modelly.provenance import RunSpec, bundle, run_study, verify
from modelly.provenance.bundle import BundleError
from modelly.provenance.llm import CACHE_FILE, FIELD, cache_problem
from modelly.provenance.verify import record_notes

ROOT = Path(__file__).resolve().parents[2]
STEPS = 3
SEED = 11
VOTERS = 5

TOWN_SOURCE = """
import json
import os

from modelly import Agent, Model
from modelly.data.collector import DataCollector
from modelly.llm import Client, FakeProvider, LLMAgent, OpenAICompatibleProvider

SCHEMA = {"properties": {"vote": {"enum": ["yes", "no"]}}, "required": ["vote"]}
CLOSED_PORT = "http://127.0.0.1:9/v1"


def answer(request):
    return json.dumps({"vote": "yes" if request.call_index % 2 else "no"})


def provider():
    if os.environ.get("TOWN_PROVIDER") == "http":
        return OpenAICompatibleProvider(base_url=CLOSED_PORT, name=FakeProvider.name)
    return FakeProvider(answer)


def yes_votes(model):
    return sum(agent.vote == "yes" for agent in model.agents)


class Voter(LLMAgent, Agent):
    persona = "You are a voter."

    def step(self):
        self.vote = self.decide("Do you vote yes or no?", SCHEMA)["vote"]


class Town(Model):
    def __init__(self, n=VOTERS, rng=None):
        super().__init__(rng=rng)
        self.llm = Client(provider(), model="town-1", max_concurrency=1)
        Voter.create_agents(self, n)
        self.datacollector = DataCollector(model_reporters={"yes": yes_votes})

    def step(self):
        self.agents.do("step")
        self.datacollector.collect(self)
""".replace("VOTERS", str(VOTERS))


@pytest.fixture
def town(tmp_path) -> str:
    """The town model as a file target."""
    folder = tmp_path / "model"
    folder.mkdir()
    path = folder / "town.py"
    path.write_text(textwrap.dedent(TOWN_SOURCE), encoding="utf-8")
    return f"{path}:Town"


@pytest.fixture
def town_run(tmp_path, town) -> Path:
    """A recorded run of the town, with the stand-in provider."""
    out = tmp_path / "runs"
    run_study(RunSpec(town, out=out, steps=STEPS, seed=SEED))
    return out


@pytest.fixture
def offline(monkeypatch):
    """The real provider, and no socket may connect anywhere."""

    def refuse(*args, **kwargs):
        raise OSError("network refused by the test")

    monkeypatch.setenv("TOWN_PROVIDER", "http")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def test_run_records_the_replies_in_the_manifest(town_run):
    """The manifest names the exported cache, its hash and how many replies it holds."""
    manifest = json.loads((town_run / "manifest.json").read_text(encoding="utf-8"))
    record = manifest[FIELD]
    assert record["path"] == CACHE_FILE
    assert record["responses"] == VOTERS * STEPS
    assert (town_run / CACHE_FILE).is_file()


def test_runs_without_a_client_record_no_cache(boltzmann_run):
    """A model with no language-model client keeps its manifest as before."""
    manifest = json.loads((boltzmann_run / "manifest.json").read_text(encoding="utf-8"))
    assert FIELD not in manifest
    assert not (boltzmann_run / CACHE_FILE).exists()


def test_bundle_verifies_with_no_network(tmp_path, town_run, offline):
    """Unpacked elsewhere, the bundle reruns from its replies alone: outputs match."""
    archive = bundle(town_run, tmp_path / "study.zip")
    with zipfile.ZipFile(archive) as opened:
        assert CACHE_FILE in opened.namelist()
        opened.extractall(tmp_path / "review")
    result = verify(tmp_path / "review" / "manifest.json")
    assert result.matches, result.difference
    assert result.notes == []


def test_without_the_cache_the_rerun_needs_the_network(town_run, offline):
    """The test really is offline: with the cache gone, the rerun cannot call out."""
    (town_run / CACHE_FILE).unlink()
    with pytest.raises(ProviderError):
        verify(town_run)


def test_a_changed_cache_is_refused_by_bundle_and_noted(tmp_path, town_run):
    """Replies emptied after the run cannot be bundled, and cannot answer a replay."""
    (town_run / CACHE_FILE).write_bytes(b"")
    with pytest.raises(BundleError, match="changed since the run"):
        bundle(town_run, tmp_path / "study.zip")
    manifest = json.loads((town_run / "manifest.json").read_text(encoding="utf-8"))
    assert "changed since the run" in cache_problem(manifest, town_run)
    assert any(
        "language-model cache" in note for note in record_notes(manifest, town_run)
    )
    with pytest.raises(CacheMiss):
        verify(town_run)


def test_a_reply_the_record_lacks_stops_the_replay(tmp_path):
    """A call the recorded cache does not hold raises CacheMiss, never a network call."""
    recorded = Client(FakeProvider(), model="town-1")
    path = recorded.cache.export(tmp_path / "replies.jsonl")
    with replaying(path):
        replay = Client(FakeProvider(), model="town-1")
        assert active_replay() is replay.cache
    with pytest.raises(CacheMiss):
        replay.complete("A question nobody asked")
    assert active_replay() is None
    assert replay.usage.calls == 0


def test_cli_bundle_verifies_offline_in_a_fresh_interpreter(tmp_path, town_run):
    """``modelly verify`` on the unpacked bundle, with the closed-port provider."""
    archive = bundle(town_run, tmp_path / "study.zip")
    with zipfile.ZipFile(archive) as opened:
        opened.extractall(tmp_path / "review")
    checked = subprocess.run(
        [sys.executable, "-m", "modelly", "verify", str(tmp_path / "review")],
        cwd=ROOT,
        env={**_environment(), "TOWN_PROVIDER": "http"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "outputs match" in checked.stdout


def _environment() -> dict[str, str]:
    """This process's environment, for the subprocess."""
    import os  # noqa: PLC0415

    return dict(os.environ)
