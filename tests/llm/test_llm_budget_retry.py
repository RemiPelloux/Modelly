"""Budgets stop a run before the call that would pass them; retries back off on 429 and 5xx."""

import threading

import pytest

from modelly.llm import (
    Budget,
    BudgetExceeded,
    Client,
    FakeProvider,
    Price,
    ProviderError,
    RetryPolicy,
)

PROMPT = "x" * 40  # 10 tokens at four characters per token
BARRIER_TIMEOUT = 10.0  # seconds; only reached when the calls do not overlap


def client_with(budget, fake=None, **options):
    """A fake client with ``budget`` and short replies."""
    return Client(fake or FakeProvider(lambda r: "ok"), budget=budget, **options)


def test_token_budget_stops_before_the_call():
    """Each call reserves prompt + max_tokens; the one that could pass is never sent."""
    fake = FakeProvider(lambda r: "ok")
    client = client_with(Budget(max_tokens=50), fake, max_tokens=10)
    client.complete(PROMPT)
    client.complete(PROMPT)
    with pytest.raises(BudgetExceeded, match="over the budget of 50"):
        client.complete(PROMPT + PROMPT + PROMPT)
    assert fake.calls == 2
    assert client.usage.calls == 2
    assert client.usage.input_tokens == 20
    assert client.usage.output_tokens == 2


def test_batch_sends_what_fits_then_stops():
    """In a batch, calls before the refusal are sent, counted and cached."""
    fake = FakeProvider(lambda r: "ok")
    client = client_with(Budget(max_tokens=45), fake, max_tokens=10)
    requests = [client.request(PROMPT) for _ in range(3)]
    with pytest.raises(BudgetExceeded, match="call 2 of 'model'"):
        client.complete_many(requests)
    assert fake.calls == 2
    assert len(client.cache) == 2


def test_cost_from_the_price_table():
    """Cost = tokens x price per million; the cost budget stops the run."""
    prices = {"fake": Price(input_per_million=1_000_000.0, output_per_million=0.0)}
    client = client_with(Budget(max_cost=25.0, prices=prices), max_tokens=1)
    client.complete(PROMPT)
    assert client.usage.cost == pytest.approx(10.0)
    client.complete(PROMPT)
    with pytest.raises(BudgetExceeded, match="cost"):
        client.complete(PROMPT)
    assert client.usage.cost == pytest.approx(20.0)


def test_cost_is_unknown_without_a_price():
    """No price: the cost is None, never a guess."""
    client = client_with(Budget(max_tokens=1000))
    client.complete(PROMPT)
    assert client.usage.cost is None


def test_cost_budget_needs_a_price():
    """A cost limit without a price for the model refuses to call at all."""
    fake = FakeProvider()
    client = client_with(Budget(max_cost=1.0), fake)
    with pytest.raises(BudgetExceeded, match="no price"):
        client.complete(PROMPT)
    assert fake.calls == 0


def test_cache_hits_cost_nothing():
    """A replayed reply is a hit: no tokens, no cost, no budget used."""
    client = client_with(Budget(max_tokens=30), max_tokens=10)
    client.complete(PROMPT, call_index=0)
    for _ in range(5):
        client.complete(PROMPT, call_index=0)
    assert (client.usage.calls, client.usage.cache_hits) == (1, 5)


def test_retries_back_off_and_succeed(delays):
    """429 then 503: two waits of 1 and 2 seconds (no real sleep), then a reply."""
    fake = FakeProvider(lambda r: "ok", failures=[429, 503])
    retry = RetryPolicy(base_delay=1.0, sleeper=delays.append)
    client = Client(fake, retry=retry)
    assert client.complete("Hi").text == "ok"
    assert delays == [1.0, 2.0]
    assert (fake.calls, client.usage.calls, client.usage.retries) == (3, 1, 2)


def test_delays_are_capped(delays):
    """Backoff doubles up to max_delay."""
    retry = RetryPolicy(
        max_retries=5, base_delay=1.0, max_delay=3.0, sleeper=delays.append
    )
    fake = FakeProvider(lambda r: "ok", failures=[500] * 5)
    Client(fake, retry=retry).complete("Hi")
    assert delays == [1.0, 2.0, 3.0, 3.0, 3.0]


def test_client_errors_are_not_retried(delays):
    """A 400 fails at once."""
    fake = FakeProvider(failures=[400])
    client = Client(fake, retry=RetryPolicy(sleeper=delays.append))
    with pytest.raises(ProviderError):
        client.complete("Hi")
    assert (fake.calls, delays) == (1, [])


def test_retries_run_out(delays):
    """After max_retries the last error is raised, and nothing is cached."""
    fake = FakeProvider(failures=[503] * 3)
    client = Client(fake, retry=RetryPolicy(max_retries=2, sleeper=delays.append))
    with pytest.raises(ProviderError, match="503"):
        client.complete("Hi")
    assert len(client.cache) == 0
    assert len(delays) == 2


def test_failed_call_in_a_batch_keeps_the_others(delays):
    """One failing call raises after the others are cached."""
    fake = FakeProvider(lambda r: "ok", failures=[400])
    client = Client(fake, retry=RetryPolicy(sleeper=delays.append), max_concurrency=1)
    with pytest.raises(ProviderError):
        client.complete_many([client.request(f"q{i}") for i in range(3)])
    assert len(client.cache) == 2


def test_concurrency_limit_is_respected():
    """No more calls in flight than max_concurrency, and replies stay in request order."""
    lock, state = threading.Lock(), {"now": 0, "peak": 0}

    def responder(request):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        with lock:
            state["now"] -= 1
        return request.messages[0].content

    client = Client(FakeProvider(responder), max_concurrency=3)
    replies = client.complete_many([client.request(f"q{i}") for i in range(30)])
    assert [r.text for r in replies] == [f"q{i}" for i in range(30)]
    assert state["peak"] <= 3


def test_invalid_concurrency():
    """At least one call must be allowed in flight."""
    with pytest.raises(ValueError, match="max_concurrency"):
        Client(FakeProvider(), max_concurrency=0)


def test_calls_really_run_concurrently():
    """Three calls meet at a barrier: they can only pass it if all are in flight at once."""
    barrier = threading.Barrier(3, timeout=BARRIER_TIMEOUT)

    def responder(request):
        barrier.wait()
        return "met"

    client = Client(FakeProvider(responder), max_concurrency=3)
    replies = client.complete_many([client.request(f"q{i}") for i in range(3)])
    assert [r.text for r in replies] == ["met"] * 3


def test_without_threads_calls_run_in_this_thread(monkeypatch):
    """Where threads cannot start (Pyodide), every call runs here, in request order."""
    monkeypatch.setattr("modelly.llm.client.THREADS", False)
    callers = set()

    def responder(request):
        callers.add(threading.get_ident())
        return request.messages[0].content

    client = Client(FakeProvider(responder), max_concurrency=4)
    replies = client.complete_many([client.request(f"q{i}") for i in range(8)])
    assert [r.text for r in replies] == [f"q{i}" for i in range(8)]
    assert callers == {threading.get_ident()}
