"""``LLMAgent``: a mixin that lets an agent ask the model's client and decide from the reply.

Each agent counts its own calls. The count and the agent's ``unique_id`` are in every
cache key it produces, so the keys do not depend on thread timing or on which other
agents asked first: a run on one thread and a run with many threads ask the cache for
the same keys. Agents have no memory of earlier calls in 1.3: each call sends the
persona and the prompt only.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from modelly.llm.client import Client
from modelly.llm.decide import DEFAULT_REPAIRS, decide_many, with_schema
from modelly.llm.request import Request

ATTRIBUTE = "llm"


def client_of(model: Any) -> Client:
    """The ``llm`` attribute of ``model``: the client its agents call."""
    client = getattr(model, ATTRIBUTE, None)
    if not isinstance(client, Client):
        raise AttributeError(
            "an LLMAgent calls model.llm: set self.llm = modelly.llm.Client(...) in the "
            "model's __init__"
        )
    return client


def model_seed(model: Any) -> int | None:
    """The seed the model's scenario derives its generators from, for cache keys."""
    scenario = getattr(model, "scenario", None)
    return getattr(scenario, "_stdlib_seed", None)


class LLMAgent:
    """Mix into an ``Agent`` (``class Voter(LLMAgent, Agent)``) to ask ``model.llm``.

    Attributes:
        persona: The system prompt of this agent's calls; the client's when empty.
        llm_calls: How many calls this agent made (including repairs).

    Example:
        >>> from modelly import Agent, Model
        >>> from modelly.llm import Client, FakeProvider
        >>> class Voter(LLMAgent, Agent):
        ...     persona = "You are a careful voter."
        >>> model = Model(rng=1)
        >>> model.llm = Client(FakeProvider())
        >>> Voter(model).ask("Vote?").startswith("fake reply")
        True
    """

    persona: str = ""
    llm_calls: int = 0

    @property
    def llm(self) -> Client:
        """The client of this agent's model."""
        return client_of(self.model)  # type: ignore[attr-defined]

    @property
    def llm_scope(self) -> str:
        """Who is asking, in cache keys and error messages."""
        return f"{type(self).__name__}:{self.unique_id}"  # type: ignore[attr-defined]

    def next_call_index(self) -> int:
        """Take this agent's next call index."""
        index = self.llm_calls
        self.llm_calls = index + 1
        return index

    def llm_request(
        self, prompt: str, *, schema: dict | None = None, **params: Any
    ) -> Request:
        """A request from this agent; with a schema, the prompt asks for JSON."""
        text = with_schema(prompt, schema) if schema is not None else prompt
        return self.llm.request(
            text,
            scope=self.llm_scope,
            call_index=self.next_call_index(),
            system=self.persona or None,
            seed=model_seed(self.model),  # type: ignore[attr-defined]
            schema=schema,
            **params,
        )

    def ask(self, prompt: str, **params: Any) -> str:
        """The reply text to ``prompt``."""
        return self.llm.complete_many([self.llm_request(prompt, **params)])[0].text

    def decide(
        self,
        prompt: str,
        schema: dict,
        *,
        repairs: int = DEFAULT_REPAIRS,
        **params: Any,
    ) -> Any:
        """A decision matching ``schema``, with up to ``repairs`` repair calls.

        Raises:
            DecisionError: When the reply is still invalid after the repairs.
        """
        return decide_all([self], prompt, schema, repairs=repairs, **params)[0]


def decide_all(
    agents: Sequence[LLMAgent],
    prompt: str | Callable[[Any], str],
    schema: dict,
    *,
    repairs: int = DEFAULT_REPAIRS,
    **params: Any,
) -> list[Any]:
    """One decision per agent, sent concurrently, returned in the order of ``agents``.

    Args:
        agents: ``LLMAgent`` instances of one model.
        prompt: The same prompt for all, or a function of the agent.
        schema: What each decision must match.
        repairs: Repair rounds for invalid replies.
        **params: Call parameters for every request.
    """
    if not agents:
        return []
    by_scope = {agent.llm_scope: agent for agent in agents}
    requests = [
        agent.llm_request(
            prompt(agent) if callable(prompt) else prompt, schema=schema, **params
        )
        for agent in agents
    ]
    client = agents[0].llm
    return decide_many(
        client, requests, lambda r: by_scope[r.scope].next_call_index(), repairs
    )
