"""LLMAgent, structured decisions with repair, stable keys across executors, checkpoints."""

import json

import pytest

from modelly import Agent, Model
from modelly.llm import (
    CacheMiss,
    Client,
    DecisionError,
    FakeProvider,
    LLMAgent,
    ResponseCache,
    decide_all,
)

VOTE = {
    "type": "object",
    "required": ["vote"],
    "properties": {"vote": {"enum": ["yes", "no"]}},
}
REPAIRED = "did not match the schema"


class Voter(LLMAgent, Agent):
    """An agent with a persona that votes through the model's client."""

    persona = "You are a voter."


def by_parity(request):
    """Odd agents vote yes, even no; the agent id is in the scope."""
    agent_id = int(request.scope.split(":")[1])
    return json.dumps({"vote": "yes" if agent_id % 2 else "no"})


def prose_first(request):
    """Answer in prose, then in JSON once asked to repair."""
    if REPAIRED in request.messages[-1].content:
        return '{"vote": "yes"}'
    return "I would say yes."


def always_prose(request):
    """Never valid."""
    return "Yes, definitely."


def build(responder, n=4, **options):
    """A seeded model with ``n`` voters and a fake client."""
    model = Model(rng=3)
    model.llm = Client(FakeProvider(responder), **options)
    voters = [Voter(model) for _ in range(n)]
    return model, voters


def test_decide_returns_validated_data():
    """A valid JSON reply comes back as data; the persona is the system prompt."""
    model, voters = build(by_parity)
    assert voters[0].decide("Vote?", VOTE) == {"vote": "yes"}
    sent = model.llm.provider.requests[0]
    assert sent.system == "You are a voter."
    assert "JSON schema" in sent.messages[0].content
    assert sent.seed is not None


def test_repair_retry_fixes_an_invalid_reply():
    """Prose fails the schema; one repair call with the reason gets valid JSON."""
    model, voters = build(prose_first)
    assert voters[0].decide("Vote?", VOTE) == {"vote": "yes"}
    repair = model.llm.provider.requests[1]
    assert [m.role for m in repair.messages] == ["user", "assistant", "user"]
    assert "no JSON value" in repair.messages[-1].content
    assert voters[0].llm_calls == 2


def test_decision_error_after_the_repairs():
    """Still invalid after the repairs: DecisionError with the reply."""
    _, voters = build(always_prose)
    with pytest.raises(DecisionError, match="Yes, definitely") as failed:
        voters[0].decide("Vote?", VOTE, repairs=2)
    assert failed.value.scope == voters[0].llm_scope
    assert voters[0].llm_calls == 3


def test_decide_all_keeps_agent_order():
    """Decisions come back in the order of the agents, each with its own counter."""
    _, voters = build(by_parity, n=9, max_concurrency=4)
    votes = decide_all(voters, lambda v: f"Vote, {v.unique_id}?", VOTE)
    assert [v["vote"] for v in votes] == [
        "yes" if v.unique_id % 2 else "no" for v in voters
    ]
    assert all(v.llm_calls == 1 for v in voters)
    assert decide_all([], "x", VOTE) == []


def run_keys(concurrency):
    """The cache keys and decisions of two rounds on ``concurrency`` threads."""
    model, voters = build(prose_first, n=12, max_concurrency=concurrency)
    votes = [decide_all(voters, "Vote?", VOTE) for _ in range(2)]
    return [row[0] for row in model.llm.cache.rows()], votes


def test_keys_do_not_depend_on_the_executor():
    """One thread or eight: the same keys, the same decisions."""
    assert run_keys(1) == run_keys(8)


def test_ask_returns_text():
    """ask() is a plain completion from the agent."""
    _, voters = build(lambda r: "hello")
    assert voters[0].ask("Hi") == "hello"


def test_agent_without_a_client():
    """An LLMAgent in a model with no llm attribute says what to set."""
    model = Model(rng=1)
    with pytest.raises(AttributeError, match=r"model\.llm"):
        Voter(model).ask("Hi")


def test_checkpoint_keeps_the_cache_and_replays(tmp_path):
    """Model.save keeps the cache and counters; the loaded run replays with no call."""
    model, voters = build(by_parity, n=5)
    first = decide_all(voters, "Vote?", VOTE)
    path = tmp_path / "run.ckpt"
    model.save(path)
    loaded = Model.load(path)
    assert len(loaded.llm.cache) == len(model.llm.cache) == 5
    assert loaded.llm.usage.calls == 5
    loaded.llm.cache.mode = "read-only"
    again = list(loaded.agents)
    for agent in again:
        agent.llm_calls = 0
    assert decide_all(again, "Vote?", VOTE) == first
    assert loaded.llm.provider.calls == model.llm.provider.calls
    with pytest.raises(CacheMiss):
        decide_all(again, "Something new?", VOTE)


def test_replay_mode_never_calls_the_provider(tmp_path):
    """A run replayed from its exported cache makes no provider call at all."""
    model, voters = build(by_parity, n=6)
    recorded = [decide_all(voters, "Vote?", VOTE) for _ in range(3)]
    path = model.llm.cache.export(tmp_path / "votes.jsonl")
    replay, again = build(by_parity, n=6, cache=ResponseCache.from_file(path))
    assert [decide_all(again, "Vote?", VOTE) for _ in range(3)] == recorded
    assert replay.llm.provider.calls == 0
    assert replay.llm.usage.cache_hits == 18
