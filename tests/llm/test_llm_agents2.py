"""Language-model agents II: memory, plans, tools, conversations, evaluation, the market."""

import itertools
import json

import numpy as np
import pytest

from modelly import Agent, Model
from modelly.llm import (
    Client,
    FakeProvider,
    MemoryAgent,
    ResponseCache,
    Tool,
    converse,
    converse_many,
    evaluate,
    plan,
    reflect,
    use_tools,
)
from modelly.llm.errors import DecisionError
from modelly.llm.market import Market, local_trader


class Person(MemoryAgent, Agent):
    """An agent with a small memory."""

    persona = "You are a person."
    memory_capacity = 4
    memory_keep = 2


def last_message(request):
    """Reply with the last message, for tests that look at prompts."""
    return request.messages[-1].content


def town(responder, n=2):
    """A model of ``n`` people answering through ``responder``."""
    model = Model(rng=3)
    model.llm = Client(FakeProvider(responder))
    people = [Person(model) for _ in range(n)]
    return model, people


def test_memory_starts_every_prompt_and_is_summarised_when_full():
    """Episodes appear in prompts; past capacity the oldest become one summary."""
    _model, (person, _) = town(last_message)
    person.remember("I met Ana.")
    assert person.ask("Hello?").startswith("What you remember:\n- [t=0] I met Ana.")
    for i in range(4):
        person.remember(f"Event {i}.")
    assert person.memory.summary.startswith("Summarise these memories")
    assert [text for _, text in person.memory.episodes] == ["Event 2.", "Event 3."]
    with pytest.raises(ValueError, match="keep"):
        type(person.memory)(capacity=2, keep=2)


def scripted(replies):
    """A responder playing back ``replies`` in order, then the last one forever."""
    queue = list(replies)

    def respond(request):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return respond


def test_plans_and_reflections_are_remembered():
    """A JSON plan is cut to its steps; a reflection becomes a memory."""
    _model, (person, _) = town(
        scripted(['{"steps": ["save", "buy", "sell", "rest"]}', "Prices rise."])
    )
    assert plan(person, "earn more", max_steps=3) == ["save", "buy", "sell"]
    assert reflect(person) == "Prices rise."
    texts = [text for _, text in person.memory.episodes]
    assert (
        texts[0] == "My plan: save; buy; sell"
        and texts[-1] == "Reflection: Prices rise."
    )


def test_tools_are_called_and_their_results_sent_back():
    """The agent asks for a price, gets it in the conversation, then answers."""
    seen = []

    def responder(request):
        seen.append(request.messages[-1].content)
        if len(request.messages) == 1:
            return json.dumps({"action": "price", "arguments": {"item": "apple"}})
        return json.dumps({"action": "answer", "answer": "buy"})

    model, (person, _) = town(responder)
    price = Tool("price", "today's price of an item", lambda item: {"apple": 2.5}[item],
                 {"item": "the item"})  # fmt: skip
    used = use_tools(person, "Should you buy apples?", [price])
    assert used.answer == "buy" and used.calls == [("price", {"item": "apple"}, 2.5)]
    assert seen[-1] == "Result of price: 2.5"
    model.llm = Client(
        FakeProvider(lambda r: '{"action": "price", "arguments": {"item": "apple"}}')
    )
    with pytest.raises(DecisionError, match="tool calls"):
        use_tools(person, "Again?", [price], max_rounds=2)


def test_conversations_take_turns_in_batches_and_are_remembered():
    """Round-robin alternates; many groups share each turn's batch; a generator orders too."""
    model, people = town(
        lambda r: f"turn {len(r.messages[-1].content.splitlines()) - 2}", n=4
    )
    transcript = converse(people[:2], "the weather", turns=3)
    assert [t.speaker for t in transcript] == [
        people[0].unique_id,
        people[1].unique_id,
        people[0].unique_id,
    ]
    calls = model.llm.provider.calls
    many = converse_many([people[:2], people[2:]], "prices", turns=2)
    assert model.llm.provider.calls - calls == 4 and len(many) == 2
    drawn = converse(people, "news", turns=6, order=np.random.default_rng(1))
    assert all(a.speaker != b.speaker for a, b in itertools.pairwise(drawn))
    assert any(
        "Conversation about the weather" in text
        for _, text in people[0].memory.episodes
    )
    with pytest.raises(ValueError, match="two agents"):
        converse(people[:1], "alone", turns=1)


def test_the_market_runs_caches_and_replays_offline(tmp_path):
    """500 traders, two rounds: recorded once, then replayed with no call at all."""
    cache = ResponseCache(tmp_path / "market.sqlite")
    live = Market(
        traders=500, rng=11, client=Client(FakeProvider(local_trader), cache=cache)
    )
    live.run_for(2)
    assert len(live.agents) == 500 and live.llm.usage.calls == 2000 and live.prices
    cache.export(tmp_path / "replies.jsonl.gz")
    silent = FakeProvider(lambda r: pytest.fail("a replay sent a call"))
    replay = Client(
        silent, cache=ResponseCache.from_file(tmp_path / "replies.jsonl.gz")
    )
    again = Market(traders=500, rng=11, client=replay)
    again.run_for(2)
    assert again.prices == live.prices and silent.calls == 0
    assert again.llm.usage.cache_hits == 2000


def test_the_evaluation_harness_compares_providers():
    """Three stand-in providers: behaviour, agreement across seeds and usage per provider."""

    def stingy(request):
        text = local_trader(request)
        return text.replace("true", "false") if '"buy"' in text else text

    clients = {
        "local": lambda: Client(FakeProvider(local_trader)),
        "stingy": lambda: Client(FakeProvider(stingy)),
        "echo": lambda: Client(FakeProvider(local_trader), model="echo-model"),
    }
    result = evaluate(lambda seed, client: Market(traders=40, rng=seed, client=client), clients,
                      seeds=[1, 2], steps=1, metrics={"trades": lambda m: len(m.prices)},
                      choices=lambda m: [a.traded for a in m.agents])  # fmt: skip
    report = result.report()
    assert list(report.index) == ["local", "stingy", "echo"]
    assert (
        report.loc["stingy", "trades_mean"] == 0
        and report.loc["local", "trades_mean"] > 0
    )
    assert report.loc["local", "calls"] == 2 * 4 * 20
    assert 0 <= report.loc["local", "agreement"] <= 1
    assert report.loc["stingy", "agreement"] == 1.0
