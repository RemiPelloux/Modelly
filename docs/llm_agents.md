# Language-model agents

`modelly.llm` lets an agent decide through a language model: give it a persona, ask it a
question, get back data checked against a schema. Every call goes through one client that
caches the reply, holds the call against a budget and retries when the provider is busy, so a
study can be rerun, replayed offline and audited.

```python
from modelly import Agent, Model
from modelly.llm import (
    AnthropicProvider,
    Budget,
    Client,
    LLMAgent,
    ResponseCache,
    decide_all,
)

STANCE = {
    "type": "object",
    "required": ["opinion"],
    "properties": {"opinion": {"enum": ["support", "neutral", "oppose"]}},
}


class Citizen(LLMAgent, Agent):
    def __init__(self, model, persona):
        super().__init__(model)
        self.persona = persona  # the system prompt of this agent's calls
        self.opinion = "neutral"


class Town(Model):
    def __init__(self, personas, rng=42):
        super().__init__(rng=rng)
        self.llm = Client(
            AnthropicProvider(),  # reads ANTHROPIC_API_KEY; model claude-sonnet-5-5
            cache=ResponseCache("town.sqlite"),
            budget=Budget(max_tokens=500_000),
            max_concurrency=8,
        )
        for persona in personas:
            Citizen(self, persona)

    def step(self):
        citizens = list(self.agents)
        decisions = decide_all(
            citizens, "What do you think of the new bike lane?", STANCE
        )
        for citizen, decision in zip(citizens, decisions):
            citizen.opinion = decision["opinion"]
```

One agent can also ask on its own: `self.decide(prompt, schema)` returns validated data and
`self.ask(prompt)` returns the reply text. `decide_all` sends a whole population's calls
concurrently (at most `max_concurrency` at once) and returns the decisions in the order of the
agents, whatever order the replies arrive in.

The full example, 200 persona agents on a friendship network, is
[`modelly/examples/llm/llm_opinions`](https://github.com/RemiPelloux/Modelly/tree/main/modelly/examples/llm/llm_opinions).
It runs offline with a local stand-in for the model and replays from a bundled cache.

## Providers

| Adapter | Endpoint | Key |
|---|---|---|
| `AnthropicProvider()` | Anthropic Messages API, `POST /v1/messages`; default model `claude-sonnet-5-5` (also `claude-opus-5-5`, `claude-haiku-5-5` through `Client(model=...)`) | `ANTHROPIC_API_KEY` or `api_key=` |
| `OpenAICompatibleProvider(base_url=...)` | any `POST /chat/completions`: OpenAI, or a local Ollama or llama.cpp server; pass `model=` to the client | `OPENAI_API_KEY`, optional for local servers |
| `FakeProvider(responder)` | a Python function of the request: tests, teaching, dry runs | none |

The adapters use the standard library only (`urllib.request`, `json`): installing Modelly
installs no provider SDK. A local model is one line:

```python
client = Client(
    OpenAICompatibleProvider(base_url="http://127.0.0.1:11434/v1", name="ollama"),
    model="llama3.2",
)
```

## Reproducibility

A language model is not a seeded generator: the same prompt can get a different reply, and a
hosted model can change or be retired. Modelly makes the *run* reproducible by recording what
the model said.

- **The cache key** is a SHA-256 of the provider name, the model, the system prompt, the
  messages, the call parameters (temperature, `max_tokens`, ...), the model's seed, the caller
  (an agent's class and `unique_id`) and the caller's call counter. Each agent counts its own
  calls, so a key does not depend on thread timing: one thread or many give the same keys.
- **Modes.** `ResponseCache(path, mode="read-write")` answers from the cache and records what
  it does not hold. `mode="read-only"` is a replay: a cache miss raises `CacheMiss` naming the
  agent, its call index and the start of the prompt, and nothing is ever sent. `mode="off"`
  always calls and stores nothing. A reply served from the cache never touches the network.
- **Checkpoints.** The client, its cache, its counters and the agents' call counters are part
  of the model, so `Model.save` writes them into the checkpoint and `Model.load` resumes with
  them.
- **Bundles.** `client.cache.export("replies.jsonl.gz")` writes every reply, sorted by key,
  with the request it answered: plain JSON lines a reviewer can read (`.jsonl`), compressed
  (`.jsonl.gz`, byte-stable) or SQLite (any other suffix). The file travels with the study;
  `ResponseCache.from_file(path)` replays it without any network.

```python
replay = Client(AnthropicProvider(), cache=ResponseCache.from_file("replies.jsonl.gz"))
model = Town(personas, rng=42)
model.llm = replay  # same seed, same prompts: every call is a cache hit
```

The store is SQLite from the standard library, in its rollback-journal mode (no WAL side
files), one transaction per reply, and exports are written to a temporary name and renamed,
so an interrupted run never leaves half a row or half a file.

A replay reproduces a run only when the run asks the same questions in the same order: same
seed, same prompts, same parameters. Change a prompt and its key changes, and the replay
reports the first call it does not hold.

## Costs and budgets

```python
from modelly.llm import Budget, Price

budget = Budget(
    max_tokens=2_000_000,
    max_cost=20.0,
    prices={"claude-sonnet-5-5": Price(input_per_million=..., output_per_million=...)},
)
client = Client(AnthropicProvider(), budget=budget)
```

- Modelly ships **no prices**: they change, and a wrong price is worse than none. Pass the
  provider's current prices; without a price, `usage.cost` is `None` and only a token budget
  can be enforced (a cost budget with a model that has no price refuses to call).
- Before a call is sent, its worst case is reserved: the prompt's estimated tokens plus its
  `max_tokens`. When that could take the run past a limit, `BudgetExceeded` is raised and the
  call is never made. In a batch, the calls before it are sent, counted and cached first, so a
  rerun with a larger budget picks up from the cache.
- `client.usage` counts the calls sent, the cache hits, the retries, the input and output
  tokens and the cost. Cache hits cost nothing.
- Rate limits (429), server errors (5xx) and lost connections are retried with exponential
  backoff (`RetryPolicy(max_retries=3, base_delay=1.0, max_delay=30.0)`), honouring the
  server's `Retry-After`. Other errors (a bad request, a missing key) fail at once.

## Structured decisions

`decide` and `decide_all` append the schema to the prompt, read the JSON value out of the
reply (plain, in a code fence or after some prose) and check it locally. The checker supports
`type` (one name or a list), `enum`, `properties`, `required`, `additionalProperties: false`,
`items`, `minimum`, `maximum`, `minLength`, `maxLength`, `minItems` and `maxItems`; any other
keyword is refused rather than silently ignored. An invalid reply gets a repair call (the same
conversation, the reply, and the reason it failed); `repairs=` sets how many rounds before
`DecisionError`. A repair is a call of its own with the agent's next call index, so a replay
asks for exactly the same repairs.

Agents have no memory of earlier calls: each call sends the persona and the prompt only. Put
what an agent should remember into its prompt.

## Privacy of API keys

- A key is read from the `api_key=` argument or from the environment
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) when the call is made.
- It is never written anywhere Modelly writes: not to the cache, not to an export, not to a
  checkpoint (a provider pickles without its key; a loaded model reads the environment again),
  not to a `repr`, not to an error message (errors name the URL and the status, never the
  headers).
- Prefer the environment to the argument, and keep the variable out of notebooks and scripts
  you share.
- The cache stores prompts and replies in full. If prompts hold personal data, the cache and
  its exports hold it too: treat them as research data under your data-protection rules.

## Ethics and limitations

- **A model is not a population.** Personas produce plausible text, not the distribution of
  views of real people. Language models carry the biases of their training data, flatten
  differences between groups and can caricature the people they are asked to play. Validate
  any finding against data from people before reading it as a finding about people.
- **Prompt sensitivity.** Small changes of wording, order or format can change decisions.
  Report the exact prompts, the schema, the model name and the parameters, and test how much
  the results move when the wording does.
- **Replay is not re-measurement.** A replay shows that the analysis follows from the recorded
  replies. It does not show that the model would answer the same way again: a hosted model can
  change under the same name. Archive the cache with the results.
- **Cost and footprint.** Every uncached call costs money and energy. Develop with
  `FakeProvider` or a small local model, cache everything, and set a budget before a large
  run.
- **Terms of use.** Follow the provider's terms and your ethics board's rules for studies that
  use generated text, especially when personas describe real groups or prompts include data
  about real people.

## Checking a model

Lint rule [MDL012](mdl012) flags a call to `requests`, `httpx`, `urllib.request.urlopen` or
the `openai` and `anthropic` SDKs inside model or agent code: such a call bypasses the cache,
so the run cannot be replayed.

The API is on the [`modelly.llm` page](apis/llm).
