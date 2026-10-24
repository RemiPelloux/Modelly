"""A stand-in for a language model, so the example runs offline and costs nothing.

It reads the prompt the way a person might: follow a clear majority of friends,
unless the persona is stubborn and the majority is not overwhelming. The hurried
commuter first answers in prose, which fails the schema, to show the repair call.
Replace it with a real provider to ask a real model (see docs/llm_agents.md).
"""

import json
import re

from modelly.examples.llm.llm_opinions.agents import OPINIONS

CURRENT = re.compile(r"current view of .*?: (\w+)\.")
HEARD = re.compile(r"(\d+) (support|neutral|oppose)")
STUBBORN = ("stubborn", "slow to change")
HURRIED = "hurried"
REPAIR_MARK = "did not match the schema"
# Share of friends a stubborn persona needs to see before it moves.
STUBBORN_MAJORITY = 0.75
SIMPLE_MAJORITY = 0.5


def town_responder(request):
    """The JSON decision a citizen would give, from the persona and the prompt alone."""
    prompt = request.messages[-1].content
    if HURRIED in request.system and REPAIR_MARK not in prompt:
        return "Honestly? I'd say I mostly support it, I guess."
    first = request.messages[0].content
    current = CURRENT.search(first).group(1)
    counts = {opinion: int(n) for n, opinion in HEARD.findall(first)}
    opinion = follow(current, counts, any(s in request.system for s in STUBBORN))
    reason = "most of my friends agree" if opinion != current else "nothing changed"
    return json.dumps({"opinion": opinion, "reason": reason})


def follow(current, counts, stubborn):
    """The majority opinion when it is large enough, else the current one."""
    total = sum(counts.values())
    if not total:
        return current
    leader = max(OPINIONS, key=lambda o: (counts.get(o, 0), o == current))
    needed = STUBBORN_MAJORITY if stubborn else SIMPLE_MAJORITY
    return leader if counts.get(leader, 0) / total > needed else current
