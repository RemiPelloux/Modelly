"""The hub: entries, indexes, search, install, publish (dry run) and the index checks."""

import hashlib
import io
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from modelly.card import Check, ModelCard, Stamp, source_digest, write_card
from modelly.hub import index as hub_index
from modelly.hub.__main__ import main
from modelly.hub.check import check_index
from modelly.hub.entry import EntryError, HubEntry, Source
from modelly.hub.index import HubError, load, search
from modelly.hub.install import install
from modelly.hub.publish import Signer, publish, zoo_index
from modelly.hub.zenodo import DryRun, Zenodo
from modelly.zoo.registry import MODELS


@pytest.fixture
def zoo_hub(tmp_path, monkeypatch):
    """The zoo index written to a file and set as the only source."""
    path = tmp_path / "index.json"
    path.write_text(json.dumps(zoo_index()), encoding="utf-8")
    monkeypatch.setenv("MODELLY_HUB", str(path))
    monkeypatch.setenv("MODELLY_CACHE", str(tmp_path / "cache"))
    return path


def package_entry(tmp_path, content=b"wheel bytes", **changes):
    """A package entry whose source is a local file with the right hash."""
    wheel = tmp_path / "demo-1.0-py3-none-any.whl"
    wheel.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    zoo = HubEntry.from_dict(zoo_index()["models"][0])
    entry = replace(
        zoo, name="demo", kind="package", source=Source("demo==1.0", str(wheel), digest)
    )
    return replace(entry, **changes)


def test_the_zoo_index_passes_the_checks_and_round_trips(zoo_hub):
    """Every zoo model is an entry with its stamped card; to_dict and from_dict agree."""
    data = zoo_index()
    assert {m["name"] for m in data["models"]} == {m.name for m in MODELS}
    assert check_index(zoo_hub) == {}
    entry = HubEntry.from_dict(data["models"][0])
    assert HubEntry.from_dict(entry.to_dict()) == entry
    assert entry.card["validated"]["source"].startswith("sha256:")


@pytest.mark.parametrize(
    ("change", "message"),
    [({"name": "Bad-Name"}, "lower case"), ({"kind": "app"}, "kind"),
     ({"target": "nocolon"}, "target"), ({"source": {"requirement": "x", "url": "u"}}, "sha256"),
     ({"extra": 1}, "unknown field"), ({"title": ""}, "missing title")],
)  # fmt: skip
def test_bad_entries_are_refused(change, message):
    """Each schema rule names its problem."""
    data = {**zoo_index()["models"][0], **change}
    with pytest.raises(EntryError, match=message):
        HubEntry.from_dict(data)


def test_search_ranks_and_filters(zoo_hub):
    """Every word must match; the name counts most; a field narrows the list."""
    hub = load()
    assert search(hub, "seir")[0].name == "age_seir"
    assert [e.name for e in search(hub, "host viral")] == ["within_host"]
    assert all(e.field == "ecology" for e in search(hub, "", "ecology"))
    assert search(hub, "no such words") == []
    with pytest.raises(KeyError, match="no model named"):
        hub.get("nothing")


def test_the_first_index_wins_and_a_url_is_cached_for_offline_use(
    tmp_path, monkeypatch
):
    """Two sources: the first one's entry stays; a URL read once is read again offline."""
    monkeypatch.setenv("MODELLY_CACHE", str(tmp_path / "cache"))
    first = zoo_index()
    second = {"schema": 1, "models": [{**first["models"][0], "title": "Other title"}]}
    body = json.dumps(second).encode()
    monkeypatch.setattr(
        hub_index.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(body)
    )
    path = tmp_path / "first.json"
    path.write_text(json.dumps(first), encoding="utf-8")
    hub = load([str(path), "https://example.org/index.json"])
    assert hub.get("age_seir").title == first["models"][0]["title"]

    def offline(*args, **kwargs):
        raise OSError("no network")

    monkeypatch.setattr(hub_index.urllib.request, "urlopen", offline)
    assert (
        load(["https://example.org/index.json"]).get("age_seir").title == "Other title"
    )
    with pytest.raises(HubError, match="cannot read"):
        load(["https://example.org/never-read.json"])


def test_installing_a_zoo_model_writes_it_into_a_folder(zoo_hub, tmp_path):
    """The model and its README, as modelly zoo copy writes them."""
    done = install(load().get("within_host"), tmp_path / "outbreak")
    assert sorted(p.name for p in done.files) == ["README.md", "model.py"]


def test_installing_a_package_checks_its_hash_then_runs_pip(tmp_path, monkeypatch):
    """The file is verified before pip sees it; a wrong hash stops everything."""
    monkeypatch.setenv("MODELLY_CACHE", str(tmp_path / "cache"))
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    done = install(package_entry(tmp_path), runner=runner)
    assert calls[0][1:4] == ["-m", "pip", "install"] and calls[0][-1].endswith(".whl")
    assert done.files[0].read_bytes() == b"wheel bytes"
    bad = package_entry(
        tmp_path, source=Source("demo==1.0", str(tmp_path / "x.whl"), "0" * 64)
    )
    (tmp_path / "x.whl").write_bytes(b"tampered")
    with pytest.raises(HubError, match="sha256"):
        install(bad, runner=runner)
    with pytest.raises(HubError, match="supports Modelly"):
        install(package_entry(tmp_path, modelly=">=99"), runner=runner)


def project(tmp_path):
    """A publishable project: pyproject, a stamped card, a model file and a wheel."""
    (tmp_path / "model.py").write_text(
        "from modelly import Model\n\n\nclass Demo(Model):\n    pass\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-model"\nversion = "0.2.0"\nkeywords = ["demo"]\n'
        'authors = [{name = "A. Modeller"}]\n\n[tool.modelly.hub]\n'
        'target = "demo_model.model:Demo"\nfield = "teaching"\n'
    )
    card = ModelCard("demo", "Demo model", "model.py:Demo", "A demo.", ("teaching",),
                     ("forecasts",), ("none",), ("tiny",), ("none foreseen",),
                     (Check("it runs", "tests/"),))  # fmt: skip
    stamp = Stamp(source_digest(card, tmp_path), "1.5.0", "2026-11-03")
    write_card(replace(card, validated=stamp), tmp_path / "card.toml")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "demo_model-0.2.0-py3-none-any.whl").write_bytes(b"wheel")
    return tmp_path


def test_publish_dry_run_shows_what_zenodo_would_receive(tmp_path):
    """The entry gets the Zenodo file URL, its hash and the DOI; nothing is sent."""
    transport = DryRun()
    done = publish(
        project(tmp_path),
        Zenodo("token", transport=transport),
        Signer("me@example.org"),
    )
    assert done.entry.doi == "10.5281/zenodo.0"
    assert done.entry.source.url.startswith(
        "https://sandbox.zenodo.org/records/0/files/"
    )
    assert done.entry.source.sha256 == hashlib.sha256(b"wheel").hexdigest()
    assert [m for m, _, _ in transport.requests] == ["POST", "PUT", "PUT", "POST"]
    assert "sigstore" in done.commands[0] and done.entry.signature is None
    assert json.loads(done.path.read_text())["name"] == "demo_model"


def test_publish_refuses_a_stale_card(tmp_path):
    """A model changed since its validation cannot be published."""
    folder = project(tmp_path)
    (folder / "model.py").write_text("changed = True\n")
    with pytest.raises(HubError, match="stale"):
        publish(folder)


def test_index_checks_find_duplicates_bad_specifiers_and_unstamped_cards(tmp_path):
    """The checks a pull request to the hub must pass."""
    entry = zoo_index()["models"][0]
    unstamped = {**entry, "name": "other", "card": {**entry["card"], "validated": None}}
    bad = {**entry, "name": "third", "modelly": "1.5"}
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"schema": 1, "models": [entry, entry, unstamped, bad]}))
    report = check_index(path)
    assert report["age_seir"] == ["the name is used twice"]
    assert report["other"] == ["card: validation never stamped"]
    assert report["third"][0].startswith("modelly:")


def test_the_command_line(zoo_hub, tmp_path, capsys):
    """search, info, install and check, against the zoo index."""
    assert main(["search", "traffic"]) == 0
    assert "road_traffic" in capsys.readouterr().out
    assert main(["info", "age_seir"]) == 0
    assert "intended use" in capsys.readouterr().out
    assert main(["install", "deffuant", str(tmp_path / "opinions")]) == 0
    assert (tmp_path / "opinions" / "model.py").is_file()
    assert main(["check", str(zoo_hub)]) == 0
    assert main(["info", "nothing"]) == 1


def test_a_signed_package_without_sigstore_warns_and_installs(tmp_path, monkeypatch):
    """The sha256 is checked; the signature cannot be, and the warning says so."""
    from modelly.hub import sign as signing  # noqa: PLC0415
    from modelly.hub.entry import Artifact  # noqa: PLC0415

    monkeypatch.setenv("MODELLY_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(signing, "available", lambda: False)
    bundle = tmp_path / "demo.whl.sigstore.json"
    bundle.write_bytes(b"{}")
    signature = Artifact(
        str(bundle), hashlib.sha256(b"{}").hexdigest(), "me@example.org", "x"
    )
    entry = package_entry(tmp_path, signature=signature)
    done = SimpleNamespace(returncode=0, stdout="", stderr="")
    with pytest.warns(RuntimeWarning, match="sigstore is not installed"):
        install(entry, runner=lambda *a, **k: done)
    assert signing.sign(bundle)[1] is None  # a dry run signs nothing
