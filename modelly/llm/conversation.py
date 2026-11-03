"""Conversations between language-model agents, turn by turn, many at once.

``converse_many(groups, topic, turns)`` runs one conversation per group of agents. In each
turn every group's next speaker is asked, with the transcript so far, and all groups' calls
of that turn are sent together, so 250 pairs of traders talk in ``turns`` rounds of
concurrent calls rather than 500 one after another. Speakers take turns in order
(``"round-robin"``) or are drawn from a generator (``order=rng``, never the same agent twice
in a row), the model's own, so a run is a function of its seed. After the conversation every
participant that has a memory remembers it.

Each call carries the speaker's scope and call counter, as every agent call does, so a
conversation replays from the cache.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

ROUND_ROBIN = "round-robin"
REPLY = "Your turn: reply in one or two sentences, as yourself."
MEMORY_CHARS = 300


@dataclass(frozen=True)
class Turn:
    """One utterance: who spoke (unique id), what, and the model's time."""

    speaker: int
    text: str
    time: float


def _prompt(topic: str, transcript: list[Turn], speaker: Any) -> str:
    """What the speaker is asked: the topic, the transcript, its turn."""
    lines = [f"You are agent {speaker.unique_id}, in a conversation about: {topic}"]
    lines += [f"Agent {turn.speaker}: {turn.text}" for turn in transcript]
    return "\n".join([*lines, REPLY])


def _next(group: Sequence[Any], turn: int, last: Any, order: Any) -> Any:
    """The speaker of ``turn``: in order, or drawn, never the last speaker again."""
    if isinstance(order, str):
        return group[turn % len(group)]
    choices = [agent for agent in group if agent is not last] or list(group)
    return choices[int(order.integers(len(choices)))]


def _remember(
    groups: Sequence[Sequence[Any]], topic: str, transcripts: Sequence[Sequence[Turn]]
) -> None:
    """Every participant with a memory remembers its conversation, shortened."""
    for group, transcript in zip(groups, transcripts):
        said = " | ".join(f"{t.speaker}: {t.text}" for t in transcript)[:MEMORY_CHARS]
        for agent in group:
            if hasattr(agent, "remember"):
                agent.remember(f"Conversation about {topic}: {said}")


def converse_many(
    groups: Sequence[Sequence[Any]], topic: str, turns: int, *, order: Any = ROUND_ROBIN,
) -> list[list[Turn]]:  # fmt: skip
    """One conversation per group; the transcripts, in the order of ``groups``.

    Args:
        groups: lists of ``LLMAgent`` instances of one model, two or more each.
        topic: what they talk about.
        turns: utterances per conversation.
        order: ``"round-robin"``, or a ``numpy`` generator to draw each next speaker.
    """
    if any(len(group) < 2 for group in groups):
        raise ValueError("a conversation needs at least two agents")
    if order != ROUND_ROBIN and not isinstance(order, np.random.Generator):
        raise ValueError(f"order is {ROUND_ROBIN!r} or a numpy Generator")
    transcripts: list[list[Turn]] = [[] for _ in groups]
    if not groups:
        return transcripts
    client = groups[0][0].llm
    for turn in range(turns):
        speakers = [
            _next(g, turn, _by_id(g, t[-1].speaker) if t else None, order)
            for g, t in zip(groups, transcripts)
        ]
        requests = [
            s.llm_request(_prompt(topic, t, s)) for s, t in zip(speakers, transcripts)
        ]
        for speaker, transcript, reply in zip(
            speakers, transcripts, client.complete_many(requests)
        ):
            transcript.append(
                Turn(speaker.unique_id, reply.text.strip(), float(speaker.model.time))
            )
    _remember(groups, topic, transcripts)
    return transcripts


def _by_id(group: Sequence[Any], unique_id: int) -> Any:
    """The agent of ``group`` with ``unique_id``."""
    return next(agent for agent in group if agent.unique_id == unique_id)


def converse(agents: Sequence[Any], topic: str, turns: int, *, order: Any = ROUND_ROBIN) -> list[Turn]:  # fmt: skip
    """One conversation among ``agents``: its transcript."""
    return converse_many([agents], topic, turns, order=order)[0]
