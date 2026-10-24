"""The HTTP adapters against a local server: request shape, reply parsing, errors, keys."""

import pickle

import pytest

from modelly.llm import (
    AnthropicProvider,
    Client,
    OpenAICompatibleProvider,
    ProviderError,
    RetryPolicy,
)
from modelly.llm.transport import retry_after

SECRET = "sk-test-secret-123"  # noqa: S105 - a fake key for the leak checks


def anthropic(server, **options):
    """A client on the local server speaking the Messages API."""
    provider = AnthropicProvider(api_key=SECRET, base_url=server.url)
    return Client(provider, retry=RetryPolicy(max_retries=0), **options)


def test_anthropic_request_and_reply(server):
    """POST /v1/messages with the key header, the version, the system prompt; text joined."""
    client = anthropic(server, system="Be brief.")
    reply = client.complete("Hi", temperature=0.5)
    sent = server.log[0]
    headers = {k.lower(): v for k, v in sent["headers"].items()}
    assert sent["path"] == "/v1/messages"
    assert headers["x-api-key"] == SECRET
    assert headers["anthropic-version"] == "2023-06-01"
    assert sent["body"]["model"] == "claude-sonnet-5-5"
    assert sent["body"]["system"] == "Be brief."
    assert sent["body"]["messages"] == [{"role": "user", "content": "Hi"}]
    assert sent["body"]["temperature"] == 0.5
    assert (reply.text, reply.input_tokens, reply.output_tokens) == (
        "Hello there",
        11,
        3,
    )


def test_anthropic_model_is_configurable(server):
    """``model=`` replaces the default Claude model."""
    anthropic(server, model="claude-haiku-5-5").complete("Hi")
    assert server.log[0]["body"]["model"] == "claude-haiku-5-5"


def test_openai_compatible_request_and_reply(server):
    """POST /chat/completions with a bearer key; the system prompt is the first message."""
    provider = OpenAICompatibleProvider(api_key=SECRET, base_url=server.url + "/v1")
    client = Client(provider, model="local-model", system="Be brief.")
    reply = client.complete("Hi")
    sent = server.log[0]
    headers = {k.lower(): v for k, v in sent["headers"].items()}
    assert sent["path"] == "/v1/chat/completions"
    assert headers["authorization"] == f"Bearer {SECRET}"
    assert sent["body"]["messages"][0] == {"role": "system", "content": "Be brief."}
    assert (reply.text, reply.input_tokens, reply.output_tokens) == ("Hi", 7, 2)


def test_local_server_needs_no_key(server, monkeypatch):
    """An Ollama-style endpoint works without any key; no auth header is sent."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAICompatibleProvider(base_url=server.url, name="ollama")
    Client(provider, model="llama").complete("Hi")
    headers = {k.lower() for k in server.log[0]["headers"]}
    assert "authorization" not in headers
    assert provider.name == "ollama"


def test_openai_needs_a_model():
    """There is no default OpenAI model: the client asks for one."""
    with pytest.raises(ValueError, match="model"):
        Client(OpenAICompatibleProvider())


def test_key_from_environment(server, monkeypatch):
    """With no api_key, ANTHROPIC_API_KEY is read at call time."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    Client(AnthropicProvider(base_url=server.url)).complete("Hi")
    headers = {k.lower(): v for k, v in server.log[0]["headers"].items()}
    assert headers["x-api-key"] == "from-env"


def test_missing_key_is_a_clear_error(monkeypatch):
    """No key anywhere: the error names the variable, and nothing is sent."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        Client(AnthropicProvider(base_url="http://127.0.0.1:9")).complete("Hi")


def test_rate_limit_is_retryable_with_retry_after(server):
    """A 429 carries its Retry-After; a 400 is not retried."""
    server.script = [
        (429, {"retry-after": "2"}, {"error": "slow down"}),
        (400, {}, {"error": "bad"}),
    ]
    client = anthropic(server)
    with pytest.raises(ProviderError) as limited:
        client.complete("Hi")
    assert (limited.value.status, limited.value.retryable) == (429, True)
    assert limited.value.retry_after == 2.0
    with pytest.raises(ProviderError) as bad:
        client.complete("Hi")
    assert (bad.value.status, bad.value.retryable) == (400, False)


def test_server_error_then_success_through_retries(server, delays):
    """Two 5xx then a reply: the client retries with backoff and counts the retries."""
    server.script = [(503, {}, {}), (500, {}, {})]
    provider = AnthropicProvider(api_key=SECRET, base_url=server.url)
    client = Client(provider, retry=RetryPolicy(base_delay=1.0, sleeper=delays.append))
    assert client.complete("Hi").text == "Hello there"
    assert delays == [1.0, 2.0]
    assert (client.usage.calls, client.usage.retries) == (1, 2)


def test_reply_that_is_not_json(server):
    """A body that is not JSON is a provider error, not a crash."""
    server.script = [(200, {}, b"<html>oops</html>")]
    with pytest.raises(ProviderError, match="not JSON"):
        anthropic(server).complete("Hi")


def test_connection_refused_is_retryable():
    """No server: a retryable error with no status."""
    provider = AnthropicProvider(api_key=SECRET, base_url="http://127.0.0.1:9")
    client = Client(provider, retry=RetryPolicy(max_retries=0))
    with pytest.raises(ProviderError) as lost:
        client.complete("Hi")
    assert lost.value.status is None
    assert lost.value.retryable


def test_key_never_leaves_memory(server):
    """The key is not in the repr, the pickle, the cache or an error message."""
    server.script = [(401, {}, {"error": "unauthorised"})]
    client = anthropic(server)
    with pytest.raises(ProviderError) as refused:
        client.complete("Hi")
    client.complete("Hi again")
    assert SECRET not in repr(client.provider)
    assert SECRET not in str(refused.value)
    assert SECRET.encode() not in pickle.dumps(client)
    assert all(SECRET not in str(row) for row in client.cache.rows())
    restored = pickle.loads(pickle.dumps(client.provider))  # noqa: S301
    assert restored._api_key is None


def test_retry_after_parsing():
    """Seconds as a number; dates and junk are ignored."""
    assert retry_after("3") == 3.0
    assert retry_after(None) is None
    assert retry_after("Wed, 21 Oct 2015 07:28:00 GMT") is None
