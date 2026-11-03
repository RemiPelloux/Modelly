"""Planning, reflection and tool use for language-model agents.

* ``plan(agent, goal)``: the agent writes a plan of a few steps, as a JSON list, and
  remembers it when it has a memory.
* ``reflect(agent)``: the agent reads its memory and writes what it has learned, which it
  remembers: the reflection loop of generative agents.
* ``use_tools(agent, prompt, tools)``: the agent may call functions of the model (look up a
  price, check its stock) before it answers. Each round it replies with a tool and its
  arguments or with its answer; a tool's result is sent back in the same conversation, and
  after ``max_rounds`` tool calls it must answer.

Every call goes through the agent's client, cached and counted like any other, so a run
with plans, reflections and tool calls replays from its cache.

Reference:
    Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P. and Bernstein, M. S.
    (2023). Generative agents: interactive simulacra of human behavior. UIST 2023.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from modelly.llm.decide import DEFAULT_REPAIRS, decide_many
from modelly.llm.errors import DecisionError

PLAN = {
    "type": "object",
    "required": ["steps"],
    "properties": {
        "steps": {"type": "array", "items": {"type": "string"}, "minItems": 1}
    },
}
ANSWER = "answer"
MAX_ROUNDS = 3


def _remember(agent: Any, text: str) -> None:
    """Record ``text`` in the agent's memory, when it has one."""
    if hasattr(agent, "remember"):
        agent.remember(text)


def plan(agent: Any, goal: str, max_steps: int = 5) -> list[str]:
    """The agent's plan toward ``goal``: at most ``max_steps`` steps."""
    prompt = f"Your goal: {goal}\nWrite a plan of at most {max_steps} short steps."
    steps = list(agent.decide(prompt, PLAN)["steps"])[:max_steps]
    _remember(agent, "My plan: " + "; ".join(steps))
    return steps


def reflect(agent: Any, question: str = "What have you learned so far?") -> str:
    """The agent's reflection on its memory, remembered."""
    text = str(agent.ask(f"{question} Answer in at most three sentences.")).strip()
    _remember(agent, f"Reflection: {text}")
    return text


@dataclass(frozen=True)
class Tool:
    """A function the agent may call.

    Attributes:
        name: how the agent calls it.
        description: what it does, shown to the agent.
        function: ``function(**arguments)``; its result is shown to the agent as JSON.
        parameters: the names of its arguments and what each is.
    """

    name: str
    description: str
    function: Callable[..., Any]
    parameters: Mapping[str, str] = field(default_factory=dict)

    def line(self) -> str:
        """One line describing the tool to the agent."""
        args = ", ".join(f"{k}: {v}" for k, v in self.parameters.items())
        return f"- {self.name}({args}): {self.description}"


@dataclass
class ToolUse:
    """The answer, and every tool call made on the way: ``(name, arguments, result)``."""

    answer: Any
    calls: list[tuple[str, dict[str, Any], Any]] = field(default_factory=list)


def _choice(tools: Sequence[Tool]) -> dict[str, Any]:
    """The schema of one round: a tool with its arguments, or the answer."""
    return {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {"enum": [t.name for t in tools] + [ANSWER]},
            "arguments": {"type": "object"},
            "answer": {},
        },
    }


def _menu(prompt: str, tools: Sequence[Tool]) -> str:
    """The first prompt: the question and the tools."""
    lines = "\n".join(t.line() for t in tools)
    return (f"{prompt}\n\nYou may call one of these tools first:\n{lines}\n"
            f'Reply with "action" set to a tool and its "arguments", or to "{ANSWER}" '
            'with your "answer".')  # fmt: skip


def use_tools(
    agent: Any, prompt: str, tools: Sequence[Tool], max_rounds: int = MAX_ROUNDS,
    repairs: int = DEFAULT_REPAIRS,
) -> ToolUse:  # fmt: skip
    """Let ``agent`` call ``tools`` before answering ``prompt``.

    Raises:
        DecisionError: when it still calls a tool after ``max_rounds`` calls.
    """
    by_name, schema = {t.name: t for t in tools}, _choice(tools)
    request = agent.llm_request(_menu(prompt, tools), schema=schema)
    result = ToolUse(None)
    for _ in range(max_rounds + 1):
        reply = decide_many(agent.llm, [request], lambda r: agent.next_call_index(), repairs)[0]  # fmt: skip
        if reply["action"] == ANSWER:
            result.answer = reply.get("answer")
            return result
        arguments = dict(reply.get("arguments") or {})
        value = by_name[reply["action"]].function(**arguments)
        result.calls.append((reply["action"], arguments, value))
        shown = json.dumps(value, default=str)
        request = request.follow_up(json.dumps(reply), f"Result of {reply['action']}: {shown}",
                                    agent.next_call_index())  # fmt: skip
    raise DecisionError(
        agent.llm_scope, json.dumps(reply), f"more than {max_rounds} tool calls"
    )
