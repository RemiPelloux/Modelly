"""Structured decisions: a reply parsed as JSON, checked against a schema, repaired once.

When a reply is not valid, the same conversation goes back with the reply and the
reason, asking for a corrected value. The repair is a call of its own, with the next
call index of the same caller, so a replay asks for exactly the same repairs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from modelly.llm.errors import DecisionError, SchemaError
from modelly.llm.request import Request
from modelly.llm.schema import describe, parse_json, validate

if TYPE_CHECKING:
    from modelly.llm.client import Client

DEFAULT_REPAIRS = 1
INSTRUCTION = "\n\nReply with only a JSON value that matches this JSON schema: {schema}"
REPAIR = (
    "Your reply did not match the schema ({reason}). Reply again with only a JSON value "
    "that matches this JSON schema: {schema}"
)


def with_schema(prompt: str, schema: dict[str, Any]) -> str:
    """``prompt`` followed by the instruction to answer in JSON matching ``schema``."""
    return prompt + INSTRUCTION.format(schema=describe(schema))


def check(text: str, schema: dict[str, Any]) -> tuple[Any, str | None]:
    """The validated value of a reply, or None and the reason it is invalid."""
    try:
        return validate(parse_json(text), schema), None
    except SchemaError as error:
        return None, str(error)


def decide_many(
    client: Client,
    requests: list[Request],
    next_index: Callable[[Request], int],
    repairs: int = DEFAULT_REPAIRS,
) -> list[Any]:
    """The validated decisions of ``requests`` (each with a ``schema``), in order.

    Args:
        client: Sends the calls.
        requests: Calls whose ``schema`` the replies must match.
        next_index: The next call index of a request's caller, for a repair call.
        repairs: Repair rounds before :class:`DecisionError` is raised.
    """
    batch = list(requests)
    replies = [r.text for r in client.complete_many(batch)]
    values: list[Any] = [None] * len(batch)
    todo = list(range(len(batch)))
    for attempt in range(repairs + 1):
        failed = []
        for i in todo:
            values[i], reason = check(replies[i], batch[i].schema or {})
            if reason is not None:
                failed.append((i, reason))
        if not failed:
            return values
        if attempt == repairs:
            i, reason = failed[0]
            raise DecisionError(batch[i].scope, replies[i], reason)
        todo = repair(client, batch, replies, failed, next_index)
    return values


def repair(
    client: Client,
    batch: list[Request],
    replies: list[str],
    failed: list[tuple[int, str]],
    next_index: Callable[[Request], int],
) -> list[int]:
    """Ask again for each failed decision; update ``batch`` and ``replies`` in place."""
    for i, reason in failed:
        prompt = REPAIR.format(reason=reason, schema=describe(batch[i].schema or {}))
        batch[i] = batch[i].follow_up(replies[i], prompt, next_index(batch[i]))
    indices = [i for i, _ in failed]
    answers = client.complete_many([batch[i] for i in indices])
    for i, answer in zip(indices, answers):
        replies[i] = answer.text
    return indices
