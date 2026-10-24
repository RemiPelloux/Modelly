"""The llm_opinions example: 200 persona agents, identical reruns, offline replay."""

import gzip

import pytest

from modelly.examples.llm.llm_opinions.model import (
    REPLAY_CACHE,
    REPLAY_STEPS,
    LLMOpinions,
    fake_client,
    record_replay,
    replay_client,
)
from modelly.examples.llm.llm_opinions.responder import town_responder
from modelly.lint import lint_paths
from modelly.llm import Budget, BudgetExceeded, CacheMiss, Client, FakeProvider


def run(client=None, steps=REPLAY_STEPS):
    """Opinions after each step, and the model."""
    model = LLMOpinions(client=client)
    history = []
    for _ in range(steps):
        model.step()
        history.append(model.opinions())
    return history, model


def test_two_runs_are_identical():
    """Same seed, same decisions, same cache, call for call."""
    first, a = run()
    second, b = run()
    assert first == second
    assert list(a.llm.cache.rows()) == list(b.llm.cache.rows())
    assert len(a.agents) == 200
    assert a.llm.usage.calls > len(a.agents)  # the repairs are calls too


def test_replay_never_calls_the_provider():
    """The bundled cache replays the run offline, with no call to any provider."""
    recorded, _ = run()
    replayed, model = run(replay_client())
    assert replayed == recorded
    assert model.llm.provider.calls == 0
    assert model.llm.usage.calls == 0
    assert model.llm.usage.cache_hits == len(model.llm.cache)


def test_bundled_cache_is_what_the_recipe_records(tmp_path):
    """record_replay() rebuilds the bundled cache: the same calls and replies, line for line.

    Compared after decompression: gzip output depends on the zlib build, so the compressed
    bytes may differ between machines while the recorded content cannot.
    """
    path = record_replay(tmp_path / REPLAY_CACHE.name)
    assert gzip.decompress(path.read_bytes()) == gzip.decompress(
        REPLAY_CACHE.read_bytes()
    )


def test_replay_past_the_recording_names_the_missing_call():
    """One step more than was recorded: a CacheMiss, not a network call."""
    with pytest.raises(CacheMiss, match="Citizen:"):
        run(replay_client(), steps=REPLAY_STEPS + 1)


def test_budget_stops_the_run_cleanly():
    """A token budget too small for one step stops before the call that would pass it."""
    fake = FakeProvider(town_responder)
    client = Client(fake, budget=Budget(max_tokens=20_000))
    with pytest.raises(BudgetExceeded):
        run(client, steps=1)
    assert client.usage.tokens <= 20_000
    assert fake.calls == client.usage.calls > 0


def test_checkpoint_round_trip(tmp_path):
    """Saved mid-run and loaded, the run continues exactly as the straight run."""
    straight, _ = run(steps=REPLAY_STEPS + 1)
    model = LLMOpinions(client=fake_client())
    model.step()
    model.save(tmp_path / "opinions.ckpt")
    loaded = LLMOpinions.load(tmp_path / "opinions.ckpt")
    rest = []
    for _ in range(REPLAY_STEPS):
        loaded.step()
        rest.append(loaded.opinions())
    assert rest == straight[1:]


def test_example_is_lint_clean():
    """The example passes every lint rule, MDL012 included."""
    assert lint_paths([REPLAY_CACHE.parents[1]]) == []
