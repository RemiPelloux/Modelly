# Opinions of persona agents (`modelly.llm`)

Two hundred citizens of a small town debate a protected bike lane. Each has a persona (a
retired teacher, a shop owner, a student who cycles, a stubborn councillor...) and sits on a
small-world friendship network. Every step each citizen is asked, with its persona as the
system prompt, what it now thinks given its friends' views. The reply must be JSON matching a
schema (`support`, `neutral` or `oppose`, with an optional reason); an invalid reply gets one
repair call. All decisions of a step are sent concurrently and applied together, in agent
order.

## Running it

By default the "language model" is a local function, `responder.town_responder`, so the
example runs offline, free and deterministically:

```python
from modelly.examples.llm.llm_opinions.model import LLMOpinions

model = LLMOpinions()
model.run_for(2)
model.llm.usage  # calls, cache hits, tokens
```

Replay the bundled cache (`resources/replay.jsonl.gz`, recorded with `record_replay()`): the
same decisions, with no call to any provider.

```python
from modelly.examples.llm.llm_opinions.model import LLMOpinions, replay_client

model = LLMOpinions(client=replay_client())
model.run_for(2)
assert model.llm.provider.calls == 0
```

To ask a real model, pass your own client, with a budget:

```python
from modelly.llm import AnthropicProvider, Budget, Client, ResponseCache

client = Client(
    AnthropicProvider(),  # reads ANTHROPIC_API_KEY
    cache=ResponseCache("opinions.sqlite"),
    budget=Budget(max_tokens=200_000),
)
model = LLMOpinions(client=client)
```

## What it shows

- Persona agents with `LLMAgent` and `decide_all`.
- Structured decisions validated against a schema, with a repair call (the hurried commuter
  first answers in prose).
- A run that replays bit for bit from its cache, offline.

The local responder follows a clear majority of friends, unless the persona is stubborn. A
real model will not behave like this function; see the limitations in the
[language-model agents guide](https://remipelloux.github.io/Modelly/llm_agents.html).
