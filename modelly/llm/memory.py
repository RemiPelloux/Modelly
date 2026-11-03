"""Memory for language-model agents: what happened to them, kept and summarised.

A ``MemoryAgent`` (mix it in instead of ``LLMAgent``) keeps a ``Memory``: episodes, each a
time and a line of text, recorded with ``remember``. Every call the agent makes starts with
what it remembers, so its decisions can depend on what it saw, said and did. Past
``capacity`` episodes, the oldest are folded into a summary by one call to the model, and
the newest ``keep`` stay verbatim: the prompt stays bounded however long the run.

The memory is an ordinary attribute of the agent, so it is saved in checkpoints with it.
The summary call is cached like every other, so a replay summarises from the cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modelly.llm.agent import LLMAgent
from modelly.llm.request import Request

CAPACITY, KEEP = 20, 10
SUMMARY_PROMPT = (
    "Summarise these memories in at most five sentences, keeping what will matter for "
    "later decisions (who did what, prices, promises, outcomes):\n"
)


@dataclass
class Memory:
    """Episodes ``(time, text)`` and a summary of the ones folded away.

    Attributes:
        capacity: episodes kept verbatim before the oldest are summarised.
        keep: episodes left verbatim after a summary.
        episodes: the verbatim episodes, oldest first.
        summary: the summary of everything older.
    """

    capacity: int = CAPACITY
    keep: int = KEEP
    episodes: list[tuple[float, str]] = field(default_factory=list)
    summary: str = ""

    def __post_init__(self) -> None:
        """Refuse a ``keep`` that would not leave room for new episodes."""
        if not 0 <= self.keep < self.capacity:
            raise ValueError("Memory needs 0 <= keep < capacity")

    def add(self, time: float, text: str) -> None:
        """Record one episode."""
        self.episodes.append((float(time), str(text)))

    @property
    def full(self) -> bool:
        """Whether the oldest episodes should be summarised."""
        return len(self.episodes) > self.capacity

    def older(self) -> str:
        """The current summary and the episodes the next summary folds away, as text."""
        lines = [f"Earlier: {self.summary}"] if self.summary else []
        cut = len(self.episodes) - self.keep
        lines += [f"[t={t:g}] {text}" for t, text in self.episodes[:cut]]
        return "\n".join(lines)

    def fold(self, summary: str) -> None:
        """Replace the older episodes with ``summary``; the newest ``keep`` stay."""
        self.episodes = self.episodes[len(self.episodes) - self.keep :]
        self.summary = summary.strip()

    def context(self) -> str:
        """What the agent remembers, as the start of a prompt; empty when nothing."""
        if not self.summary and not self.episodes:
            return ""
        lines = ["What you remember:"]
        if self.summary:
            lines.append(f"Earlier: {self.summary}")
        lines += [f"- [t={t:g}] {text}" for t, text in self.episodes]
        return "\n".join(lines)


class MemoryAgent(LLMAgent):
    r"""An ``LLMAgent`` whose calls start with its memory.

    Attributes:
        memory_capacity, memory_keep: the sizes of each agent's ``Memory``.

    Example:
        >>> from modelly import Agent, Model
        >>> from modelly.llm import Client, FakeProvider
        >>> class Trader(MemoryAgent, Agent):
        ...     persona = "You trade apples."
        >>> model = Model(rng=1)
        >>> model.llm = Client(FakeProvider(lambda r: r.messages[-1].content[:21]))
        >>> trader = Trader(model)
        >>> trader.remember("I sold 3 apples at 2.")
        >>> trader.ask("Price?")
        'What you remember:\n- '
    """

    memory_capacity: int = CAPACITY
    memory_keep: int = KEEP

    @property
    def memory(self) -> Memory:
        """This agent's memory, made on first use."""
        if "_memory" not in self.__dict__:
            self._memory = Memory(self.memory_capacity, self.memory_keep)
        return self._memory

    def remember(self, text: str) -> None:
        """Record an episode at the model's time; summarise when the memory is full."""
        self.memory.add(self.model.time, text)  # type: ignore[attr-defined]
        if self.memory.full:
            self.summarise()

    def summarise(self) -> None:
        """Fold the older episodes into a summary written by the model."""
        request = LLMAgent.llm_request(self, SUMMARY_PROMPT + self.memory.older())
        self.memory.fold(self.llm.complete_many([request])[0].text)

    def llm_request(
        self, prompt: str, *, schema: dict[str, Any] | None = None, **params: Any
    ) -> Request:
        """A request whose prompt starts with what the agent remembers."""
        context = self.memory.context()
        text = f"{context}\n\n{prompt}" if context else prompt
        return super().llm_request(text, schema=schema, **params)
