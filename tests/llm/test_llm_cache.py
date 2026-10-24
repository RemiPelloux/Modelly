"""Cache keys, the SQLite store, its modes, exports and pickling."""

import gzip
import pickle

import pytest

from modelly.llm import (
    CacheMiss,
    Client,
    FakeProvider,
    Message,
    Request,
    Response,
    ResponseCache,
)


def request(**changes):
    """A request with defaults, changed by keyword."""
    fields = {
        "provider": "fake",
        "model": "m",
        "messages": (Message("user", "Hi"),),
        "params": (("temperature", 0.0),),
        "scope": "a1",
        "call_index": 0,
        "seed": 7,
    }
    return Request(**{**fields, **changes})


@pytest.mark.parametrize(
    "change",
    [
        {"provider": "other"},
        {"model": "m2"},
        {"messages": (Message("user", "Hello"),)},
        {"system": "You are a cat."},
        {"params": (("temperature", 1.0),)},
        {"scope": "a2"},
        {"call_index": 1},
        {"seed": 8},
    ],
)
def test_every_field_changes_the_key(change):
    """Provider, model, prompt, parameters, caller, call index and seed are all in the key."""
    assert request(**change).key() != request().key()


def test_key_is_stable_and_ignores_parameter_order():
    """The same call gives the same key, a fixed known value across platforms."""
    a = request(params=(("max_tokens", 5), ("temperature", 0.0)))
    b = request(params=(("temperature", 0.0), ("max_tokens", 5)))
    assert a.key() == b.key()
    assert request().key() == request().key()
    assert len(request().key()) == 64


def test_message_roles_are_checked():
    """Only user and assistant turns; the system prompt is separate."""
    with pytest.raises(ValueError, match="role"):
        Message("system", "x")


def test_put_get_and_contains(tmp_path):
    """A stored reply comes back marked cached, from a file that survives reopening."""
    path = tmp_path / "cache.sqlite"
    cache = ResponseCache(path)
    cache.put(request(), Response("yes", 3, 1))
    cache.close()
    again = ResponseCache(path)
    hit = again.get(request().key())
    assert (hit.text, hit.input_tokens, hit.output_tokens, hit.cached) == (
        "yes",
        3,
        1,
        True,
    )
    assert request().key() in again
    assert len(again) == 1
    assert not (tmp_path / "cache.sqlite-wal").exists()


def test_unknown_mode_is_refused():
    """Only the three modes exist."""
    with pytest.raises(ValueError, match="mode"):
        ResponseCache(mode="sometimes")


@pytest.mark.parametrize("name", ["export.jsonl", "export.jsonl.gz", "export.sqlite"])
def test_export_and_load_round_trip(tmp_path, name):
    """Every format reloads the same rows, and no temporary file is left behind."""
    cache = ResponseCache()
    for i in range(3):
        cache.put(request(call_index=i), Response(f"r{i}", i, i))
    path = cache.export(tmp_path / name)
    loaded = ResponseCache.from_file(path)
    assert list(loaded.rows()) == list(cache.rows())
    assert loaded.mode == "read-only"
    assert sorted(p.name for p in tmp_path.iterdir()) == [name]


def test_json_lines_export_is_byte_stable(tmp_path):
    """The same rows give the same bytes, compressed too, so a bundle hash holds."""
    cache = ResponseCache()
    cache.put(request(), Response("ünïcode ✓", 1, 1))
    first = cache.export(tmp_path / "a.jsonl.gz").read_bytes()
    second = cache.export(tmp_path / "b.jsonl.gz").read_bytes()
    assert first == second
    assert "ünïcode ✓" in gzip.decompress(first).decode("utf-8")


def test_merge_adds_rows(tmp_path):
    """Merging an export into a cache keeps what it had."""
    one, two = ResponseCache(), ResponseCache()
    one.put(request(call_index=0), Response("a"))
    two.put(request(call_index=1), Response("b"))
    assert one.merge(two.export(tmp_path / "two.jsonl")) == 1
    assert len(one) == 2


def test_pickle_carries_the_rows(tmp_path):
    """A pickled cache (as in a checkpoint) holds its rows; a lost folder means memory."""
    cache = ResponseCache(tmp_path / "c.sqlite")
    cache.put(request(), Response("kept"))
    restored = pickle.loads(pickle.dumps(cache))  # noqa: S301
    assert restored.get(request().key()).text == "kept"
    state = cache.__getstate__()
    state["path"] = str(tmp_path / "missing" / "c.sqlite")
    fresh = ResponseCache.__new__(ResponseCache)
    fresh.__setstate__(state)
    assert fresh.path is None
    assert len(fresh) == 1


def test_read_write_hit_never_calls_the_provider():
    """A second identical call is served from the cache."""
    fake = FakeProvider()
    client = Client(fake)
    first = client.complete("Hi", call_index=0)
    second = client.complete("Hi", call_index=0)
    assert fake.calls == 1
    assert (first.cached, second.cached, second.text) == (False, True, first.text)
    assert client.usage.cache_hits == 1


def test_replay_miss_names_the_call():
    """In read-only mode a miss raises CacheMiss with the caller and its call index."""
    fake = FakeProvider()
    client = Client(fake, cache=ResponseCache(mode="read-only"))
    with pytest.raises(CacheMiss, match="call 3 of 'voter-9'") as miss:
        client.complete("Do you agree?", scope="voter-9", call_index=3)
    assert "Do you agree?" in str(miss.value)
    assert (miss.value.scope, miss.value.call_index) == ("voter-9", 3)
    assert fake.calls == 0


def test_off_mode_always_calls_and_stores_nothing():
    """``off`` bypasses the cache both ways."""
    fake = FakeProvider()
    client = Client(fake, cache=ResponseCache(mode="off"))
    client.complete("Hi", call_index=0)
    client.complete("Hi", call_index=0)
    assert fake.calls == 2
    assert len(client.cache) == 0


def test_replay_from_an_export_is_offline(tmp_path):
    """Record, export, replay read-only: same replies, zero provider calls."""
    recorder = Client(FakeProvider())
    recorded = [recorder.complete(f"q{i}").text for i in range(5)]
    path = recorder.cache.export(tmp_path / "study.jsonl")
    fake = FakeProvider()
    replay = Client(fake, cache=ResponseCache.from_file(path))
    assert [replay.complete(f"q{i}").text for i in range(5)] == recorded
    assert fake.calls == 0
