"""Language-model agents with runs that replay and costs that stay bounded.

Every call goes through a :class:`Client`: it builds the request, answers from the
:class:`ResponseCache` when it can, holds the call against the :class:`Budget`, sends
it with retries and a concurrency limit, and caches the reply. Agents mix in
:class:`LLMAgent` and call ``self.decide(prompt, schema)``; ``decide_all`` asks a whole
population at once and returns the decisions in agent order.

Adapters: :class:`AnthropicProvider` (Messages API), :class:`OpenAICompatibleProvider`
(OpenAI and local servers such as Ollama or llama.cpp) and :class:`FakeProvider`
(tests and teaching). They use the standard library only; no provider SDK is needed.

Example:
    >>> from modelly import Agent, Model
    >>> from modelly.llm import Client, FakeProvider, LLMAgent
    >>> class Voter(LLMAgent, Agent):
    ...     persona = "You are a voter."
    >>> model = Model(rng=7)
    >>> model.llm = Client(FakeProvider(lambda r: '{"vote": "yes"}'))
    >>> Voter(model).decide("Vote?", {"properties": {"vote": {"enum": ["yes", "no"]}}})
    {'vote': 'yes'}

See ``docs/llm_agents.md`` for reproducibility, budgets, keys and limitations.
"""

from modelly.llm.agent import LLMAgent, decide_all
from modelly.llm.budget import Budget, Price, Usage
from modelly.llm.cache import ResponseCache
from modelly.llm.client import Client
from modelly.llm.errors import (
    BudgetExceeded,
    CacheMiss,
    DecisionError,
    LLMError,
    ProviderError,
    SchemaError,
)
from modelly.llm.fake import FakeProvider
from modelly.llm.providers import AnthropicProvider, OpenAICompatibleProvider, Provider
from modelly.llm.request import Message, Request, Response
from modelly.llm.retry import RetryPolicy
from modelly.llm.schema import parse_json, validate

__all__ = [
    "AnthropicProvider",
    "Budget",
    "BudgetExceeded",
    "CacheMiss",
    "Client",
    "DecisionError",
    "FakeProvider",
    "LLMAgent",
    "LLMError",
    "Message",
    "OpenAICompatibleProvider",
    "Price",
    "Provider",
    "ProviderError",
    "Request",
    "Response",
    "ResponseCache",
    "RetryPolicy",
    "SchemaError",
    "Usage",
    "decide_all",
    "parse_json",
    "validate",
]
