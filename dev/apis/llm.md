# LLM

Language-model agents: the client, its cache, budgets, retries, providers and structured decisions. How to use them is in [Language-model agents](https://remipelloux.github.io/Modelly/dev/llm_agents.html).

Language-model agents with runs that replay and costs that stay bounded.

Every call goes through a [`Client`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Client): it builds the request, answers from the [`ResponseCache`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.ResponseCache) when it can, holds the call against the [`Budget`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Budget), sends it with retries and a concurrency limit, and caches the reply. Agents mix in [`LLMAgent`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.LLMAgent) and call `self.decide(prompt, schema)`; `decide_all` asks a whole population at once and returns the decisions in agent order.

Adapters: [`AnthropicProvider`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.AnthropicProvider) (Messages API), [`OpenAICompatibleProvider`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.OpenAICompatibleProvider) (OpenAI and local servers such as Ollama or llama.cpp) and [`FakeProvider`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.FakeProvider) (tests and teaching). They use the standard library only; no provider SDK is needed.

Example

```default
>>> from modelly import Agent, Model
>>> from modelly.llm import Client, FakeProvider, LLMAgent
>>> class Voter(LLMAgent, Agent):
...     persona = "You are a voter."
>>> model = Model(rng=7)
>>> model.llm = Client(FakeProvider(lambda r: '{"vote": "yes"}'))
>>> Voter(model).decide("Vote?", {"properties": {"vote": {"enum": ["yes", "no"]}}})
{'vote': 'yes'}
```

Agents with more: `MemoryAgent` (episodic memory, summarised), `plan`, `reflect` and `use_tools` (`modelly.llm.reasoning`), `converse` and `converse_many` (`modelly.llm.conversation`) and `evaluate`, a harness reporting behaviour, consistency and cost per provider (`modelly.llm.evaluate`). `modelly.llm.market` is a 500-trader conversational market that runs offline.

See `docs/llm_agents.md` for reproducibility, budgets, keys and limitations.

## Client and agents

#### `class Client(provider: Provider, *, model: str | None = None, cache: ResponseCache | None = None, budget: Budget | None = None, retry: RetryPolicy | None = None, max_concurrency: int = 4, system: str = '', seed: int | None = None, **params: Any)`

Language-model calls with a cache, a budget, retries and a concurrency limit.

**Parameters:**

- **provider** – The adapter: `AnthropicProvider`, `OpenAICompatibleProvider` or `FakeProvider`.
- **model** – The model name; the provider’s default when None.
- **cache** – Where replies are kept; a fresh in-memory cache when None. Inside `modelly.llm.replay.replaying`, the replayed cache instead.
- **budget** – Token and cost limits; no limit when None.
- **retry** – How failed calls are retried.
- **max_concurrency** – The most calls in flight at once.
- **system** – The system prompt used when a call sets none.
- **seed** – Part of every cache key; agents pass their model’s seed instead.
- ****params** – Default call parameters (`temperature`, `max_tokens`, …).

Example

```default
>>> from modelly.llm import FakeProvider
>>> client = Client(FakeProvider())
>>> client.complete("Hello").cached
False
>>> client.usage.calls
1
```

Set the provider and the defaults of every call.

#### `property usage: Usage`

Calls, cache hits, retries, tokens and cost so far.

#### `next_index(scope: str) → int`

The next call counter of `scope`, for calls not made by an `LLMAgent`.

#### `request(prompt: str | Sequence[Message], *, scope: str = 'model', call_index: int | None = None, system: str | None = None, seed: int | None = None, schema: dict[str, Any] | None = None, **params: Any) → Request`

Build a [`Request`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Request); `prompt` is a user message or a list of messages.

#### `complete(prompt: str | Sequence[Message], **options: Any) → Response`

One call: options are those of [`request()`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Client.request).

#### `complete_many(requests: Iterable[Request]) → list[Response]`

Replies to `requests`, in their order.

Cached replies come first and cost nothing. The calls left are held against the budget in order; up to the first that could pass it, they are sent concurrently, counted and cached, then [`BudgetExceeded`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.BudgetExceeded) is raised for the rest.

**Raises:**

- [**CacheMiss**](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.CacheMiss) – In replay mode, for the first call the cache does not hold.
- [**BudgetExceeded**](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.BudgetExceeded) – Before the first call that could pass the budget.
- [**ProviderError**](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.ProviderError) – The first call (in order) that failed after its retries.

#### `lookup(request: Request) → Response | None`

The cached reply of `request`; a miss in replay mode raises.

#### `lookup_many(batch: Sequence[Request]) → list[Response | None]`

The cached reply of each request (one query); a miss in replay mode raises.

Hits are counted in order up to the first miss in replay mode, as one [`lookup()`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Client.lookup) per request would.

#### `reserve(batch: list[Request], pending: list[int]) → tuple[list[int], BudgetExceeded | None]`

The pending calls the budget allows, and the refusal that stopped the rest.

#### `dispatch(batch: list[Request], replies: list[Response | None], allowed: list[int]) → None`

Send the `allowed` calls, then count and cache their replies in order.

#### `collect_all(batch: list[Request], replies: list[Response | None], allowed: list[int], futures: list[Future[Any]]) → list[ProviderError]`

Count every finished call in order; cache the replies in one transaction.

#### `executor() → ThreadPoolExecutor`

The client’s thread pool, made on first use and kept for later batches.

Its threads stop when the client is collected; a pickle leaves it out.

#### `send_here(request: Request) → Future[Any]`

Send `request` in this thread; its outcome as a finished future.

#### `collect(request: Request, future: Future[Any], replies: list[Response | None], index: int, stored: list[tuple[Request, Response]]) → ProviderError | None`

Count one finished call and queue it in `stored` to cache, or return its error.

#### `class LLMAgent`

Mix into an `Agent` (`class Voter(LLMAgent, Agent)`) to ask `model.llm`.

**Variables:**

- **persona** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The system prompt of this agent’s calls; the client’s when empty.
- **llm_calls** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – How many calls this agent made (including repairs).

Example

```default
>>> from modelly import Agent, Model
>>> from modelly.llm import Client, FakeProvider
>>> class Voter(LLMAgent, Agent):
...     persona = "You are a careful voter."
>>> model = Model(rng=1)
>>> model.llm = Client(FakeProvider())
>>> Voter(model).ask("Vote?").startswith("fake reply")
True
```

#### `property llm: Client`

The client of this agent’s model.

#### `property llm_scope: str`

Who is asking, in cache keys and error messages.

#### `next_call_index() → int`

Take this agent’s next call index.

#### `llm_request(prompt: str, *, schema: dict[str, Any] | None = None, **params: Any) → Request`

A request from this agent; with a schema, the prompt asks for JSON.

#### `ask(prompt: str, **params: Any) → str`

The reply text to `prompt`.

#### `decide(prompt: str, schema: dict[str, Any], *, repairs: int = 1, **params: Any) → Any`

A decision matching `schema`, with up to `repairs` repair calls.

**Raises:**

[**DecisionError**](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.DecisionError) – When the reply is still invalid after the repairs.

#### `decide_all(agents: Sequence[LLMAgent], prompt: str | Callable[[Any], str], schema: dict[str, Any], *, repairs: int = 1, **params: Any) → list[Any]`

One decision per agent, sent concurrently, returned in the order of `agents`.

**Parameters:**

- **agents** – `LLMAgent` instances of one model.
- **prompt** – The same prompt for all, or a function of the agent.
- **schema** – What each decision must match.
- **repairs** – Repair rounds for invalid replies.
- ****params** – Call parameters for every request.

## Requests and replies

#### `class Request(provider: str, model: str, messages: tuple[Message, ...], system: str = '', params: tuple[tuple[str, Any], ...] = (), scope: str = 'model', call_index: int = 0, seed: int | None = None, schema: dict[str, Any] | None = None)`

Everything that decides a reply, and who asked.

`scope` and `call_index` say which caller made the call and how many it made before: an agent’s id and its own call counter. They are part of the cache key, so two agents asking the same question get their own replies, and the key of a call does not depend on which thread sent it.

Example

```default
>>> r = Request("fake", "m", (Message("user", "Hi"),), scope="a1", call_index=0)
>>> len(r.key())
64
```

#### `property max_tokens: int | None`

The `max_tokens` parameter, the most the reply may use.

#### `identity() → dict[str, Any]`

The fields the cache key hashes, as plain JSON values.

#### `key() → str`

SHA-256 of the canonical JSON of [`identity()`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Request.identity): the cache key.

Computed once per request and kept outside the dataclass fields, so it takes no part in equality, hashing, `repr` or pickles.

#### `prompt_chars() → int`

Characters in the system prompt and every message.

#### `excerpt() → str`

The start of the last message, for error messages.

#### `follow_up(reply: str, prompt: str, call_index: int) → Request`

This conversation, the model’s `reply`, then a new user `prompt`.

#### `class Response(text: str, input_tokens: int = 0, output_tokens: int = 0, cached: bool = False, key: str = '')`

A reply: its text, the tokens it used, and whether it came from the cache.

#### `property tokens: int`

Input plus output tokens.

#### `class Message(role: str, content: str)`

One turn of a conversation: who spoke (`"user"` or `"assistant"`) and what.

## Cache

#### `class ResponseCache(path: str | Path | None = None, mode: str = 'read-write')`

Replies by cache key, in memory (`path=None`) or in a SQLite file.

**Parameters:**

- **path** – The SQLite file; created when missing. None keeps the cache in memory.
- **mode** – `"read-write"`, `"read-only"` or `"off"`.

Open (or create) the store.

#### `classmethod from_file(path: str | Path, mode: str = 'read-only') → ResponseCache`

An in-memory cache filled from an exported file (JSON lines or SQLite).

The file itself is never written, so a cache shipped with a study bundle or a package stays as it was.

#### `property reads: bool`

Whether lookups are made (every mode but `"off"`).

#### `property writes: bool`

Whether new replies are stored (`"read-write"` only).

#### `get(key: str) → Response | None`

The stored reply for `key`, marked `cached`, or None.

#### `get_many(keys: Sequence[str]) → dict[str, Response]`

The stored replies among `keys`, by key, marked `cached`.

One `SELECT ... IN` per `IN_CHUNK` keys rather than one per key.

#### `put(request: Request, response: Response) → None`

Store `response` under the key of `request`, in one transaction.

#### `put_many(pairs: Iterable[tuple[Request, Response]]) → None`

Store each `(request, response)` pair, all in one transaction.

#### `insert(rows: list[tuple[Any, ...]]) → None`

Write `rows` (in `COLUMNS` order) atomically.

#### `rows() → Iterator[tuple[Any, ...]]`

Every stored row, sorted by key.

#### `export(path: str | Path) → Path`

Write the cache to `path`: JSON lines for `.jsonl` (`.jsonl.gz`), else SQLite.

The file is written next to its target and renamed over it, so a reader never sees half a file.

#### `merge(path: str | Path) → int`

Add every row of an exported file; return how many rows it held.

#### `close() → None`

Close the connection.

Replay a recorded response cache for every client built inside a block.

`modelly verify` reruns a study whose model builds its own `Client`, often with a real provider and an empty cache. Inside `with replaying(path):` every client created takes the cache exported to `path` instead, in read-only mode: a recorded call is answered from it, an unrecorded one raises `CacheMiss`, and no call ever reaches the network.

Example

```default
>>> from modelly.llm import Client, FakeProvider, ResponseCache
>>> recorded = Client(FakeProvider(lambda request: "yes"))
>>> _ = recorded.complete("Vote?")
>>> path = recorded.cache.export("replies.jsonl")
>>> with replaying(path):
...     replay = Client(FakeProvider(lambda request: "no"))
>>> replay.complete("Vote?").text, replay.usage.calls
('yes', 0)
```

#### `active_replay() → ResponseCache | None`

The cache every new client replays from, or None outside `replaying`.

#### `replaying(path: str | Path) → Iterator[ResponseCache]`

Make every client created in the block answer only from the file at `path`.

The file (JSON lines or SQLite, as `ResponseCache.export` writes it) is read into memory and never written.

## Budgets and retries

#### `class Budget(max_tokens: int | None = None, max_cost: float | None = None, prices: Mapping[str, ~modelly.llm.budget.Price]=<factory>, usage: Usage = <factory>)`

Limits for one run and the usage counted against them.

**Parameters:**

- **max_tokens** – The most input plus output tokens the run may send for. None: no limit.
- **max_cost** – The most the run may cost. Needs a price for every model it calls.
- **prices** – Model name to [`Price`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Price).

#### `estimate(request: Request) → tuple[int, int]`

Worst-case (input, output) tokens of `request`.

#### `price_of(model: str) → Price | None`

The price of `model`; required when a cost budget is set.

#### `reserve(request: Request) → None`

Hold the worst case of `request`, or raise [`BudgetExceeded`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.BudgetExceeded).

#### `refuse_over(tokens: int, cost: float, request: Request) → None`

Raise when `tokens` or `cost` passes its limit.

#### `release(request: Request) → None`

Give back the reservation of `request` once its reply is counted.

#### `record(request: Request, response: Response, retries: int) → None`

Count a reply from the provider.

#### `record_hit() → None`

Count a reply served from the cache.

#### `class Price(input_per_million: float, output_per_million: float)`

Price per million input tokens and per million output tokens, in any currency.

#### `cost(input_tokens: int, output_tokens: int) → float`

The price of one call.

#### `class Usage(calls: int = 0, cache_hits: int = 0, retries: int = 0, input_tokens: int = 0, output_tokens: int = 0, cost: float | None = 0.0)`

What a run used so far.

**Variables:**

- **calls** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Calls sent to the provider (retries not included).
- **cache_hits** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Replies served from the cache.
- **retries** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Extra tries after a 429, a 5xx or a lost connection.
- **input_tokens** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Prompt tokens of the calls sent.
- **output_tokens** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – Reply tokens of the calls sent.
- **cost** ([*float*](https://docs.python.org/3/builtins/functions.html#float)* | **None*) – The cost of the calls sent, or None when a model has no price.

#### `property tokens: int`

Input plus output tokens.

#### `class RetryPolicy(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0, sleeper: ~collections.abc.Callable[[float], None] = <built-in function sleep>)`

How many times to retry a failed call and how long to wait in between.

**Parameters:**

- **max_retries** – Extra tries after the first; 0 never retries.
- **base_delay** – Seconds before the first retry; doubled each time after.
- **max_delay** – The longest wait, also capping a server’s `Retry-After`.
- **sleeper** – Called with the seconds to wait; `time.sleep` by default.

Example

```default
>>> RetryPolicy(base_delay=1.0).delay(2, None)
4.0
```

#### `sleeper()`

sleep(seconds)

Delay execution for a given number of seconds. The argument may be a floating-point number for subsecond precision.

#### `delay(attempt: int, retry_after: float | None) → float`

Seconds to wait before retry number `attempt` (counting from 0).

#### `run(send: Callable[[Request], Response], request: Request) → tuple[Response, int]`

`send(request)`, retried on a retryable error; return the reply and the retries.

## Providers

#### `class Provider(*, api_key: str | None = None, base_url: str | None = None, timeout: float = 120.0)`

The interface of every adapter: a `name` and [`complete()`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.Provider.complete).

Subclasses set `name` (part of every cache key), `default_model` and `key_variable`, the environment variable holding the API key.

Keep the endpoint; the key stays in memory only.

#### `static default_url() → str`

The endpoint used when `base_url` is None.

#### `api_key(required: bool = True) → str | None`

The explicit key, else the environment’s; raise when one is required.

#### `complete(request: Request) → Response`

Send `request` and return the reply.

#### `class AnthropicProvider(*, api_key: str | None = None, base_url: str | None = None, timeout: float = 120.0)`

The Anthropic Messages API (`POST /v1/messages`); key from `ANTHROPIC_API_KEY`.

Example

```default
>>> AnthropicProvider(api_key="sk-...")
AnthropicProvider(base_url='https://api.anthropic.com')
```

Keep the endpoint; the key stays in memory only.

#### `static default_url() → str`

The endpoint used when `base_url` is None.

#### `complete(request: Request) → Response`

Call the Messages API and join the text blocks of the reply.

#### `class OpenAICompatibleProvider(*, name: str | None = None, **options: Any)`

Any `POST /chat/completions` endpoint: OpenAI, or a local Ollama or llama.cpp.

The key comes from `OPENAI_API_KEY` and is optional, since local servers need none. `name` is part of the cache key: give each endpoint its own when they serve different models under one name.

Example

```default
>>> OpenAICompatibleProvider(base_url="http://127.0.0.1:11434/v1", name="ollama")
OpenAICompatibleProvider(base_url='http://127.0.0.1:11434/v1')
```

Set the endpoint, and a `name` for its cache keys.

#### `static default_url() → str`

The endpoint used when `base_url` is None.

#### `complete(request: Request) → Response`

Call chat completions; the system prompt is the first message.

#### `class FakeProvider(responder: ~collections.abc.Callable[[~modelly.llm.request.Request], str] = <function echo>, failures: ~collections.abc.Iterable[int] = ())`

Replies come from `responder(request) -> str`; tokens are counted from length.

**Parameters:**

- **responder** – A module-level function (so a model holding it can be saved).
- **failures** – HTTP statuses to raise, one per call, before answering normally: `failures=[429, 503]` fails twice, then replies.

Example

```default
>>> from modelly.llm import Client
>>> client = Client(FakeProvider(lambda request: "yes"))
>>> client.complete("Agree?").text
'yes'
```

Keep the responder and the failures to play back.

#### `complete(request: Request) → Response`

Fail with the next queued status, if any; otherwise call the responder.

## Schemas

#### `validate(value: Any, schema: dict[str, Any], path: str = '$') → Any`

Return `value` when it matches `schema`; raise [`SchemaError`](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.SchemaError) otherwise.

**Parameters:**

- **value** – Parsed JSON.
- **schema** – A schema using the supported keywords.
- **path** – Where `value` sits, for the error message.

#### `parse_json(text: str) → Any`

The JSON value in a reply: plain, inside a code fence, or after some prose.

**Raises:**

[**SchemaError**](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.SchemaError) – When the reply holds no JSON value.

## Errors

#### `exception LLMError`

Base class of every error raised by `modelly.llm`.

#### `exception ProviderError(message: str, *, status: int | None = None, retry_after: float | None = None, retryable: bool | None = None)`

A provider refused or failed a call.

**Variables:**

- **status** – The HTTP status, or None when no response came back.
- **retryable** – Whether the same call may succeed later (429, 5xx, a lost connection).
- **retry_after** – Seconds the server asked to wait, when it said so.

Record the status and whether another try may succeed (from it, by default).

#### `exception CacheMiss(scope: str, call_index: int, key: str, excerpt: str)`

A replay (`mode="read-only"`) asked for a response the cache does not hold.

**Variables:**

- **scope** – Who made the call (an agent’s id, or the scope passed to the client).
- **call_index** – The caller’s call counter for this call.
- **key** – The cache key that was looked up.

Name the call, so the user can see which prompt was never recorded.

#### `exception BudgetExceeded`

The next call could take the run past its token or cost budget.

Raised before that call is sent, so the money is never spent. Responses already received in the same batch are cached and counted first.

#### `exception SchemaError(path: str, problem: str)`

A value does not match a schema; `path` points at the first mismatch.

Say where the value breaks the schema and how.

#### `exception DecisionError(scope: str, reply: str, reason: str)`

A model reply stayed invalid after every repair attempt.

**Variables:**

- **scope** – Who asked.
- **reply** – The last reply received.

Keep the reply so the prompt or the schema can be fixed.

## Memory, reasoning, conversations and evaluation

Memory for language-model agents: what happened to them, kept and summarised.

A `MemoryAgent` (mix it in instead of `LLMAgent`) keeps a `Memory`: episodes, each a time and a line of text, recorded with `remember`. Every call the agent makes starts with what it remembers, so its decisions can depend on what it saw, said and did. Past `capacity` episodes, the oldest are folded into a summary by one call to the model, and the newest `keep` stay verbatim: the prompt stays bounded however long the run.

The memory is an ordinary attribute of the agent, so it is saved in checkpoints with it. The summary call is cached like every other, so a replay summarises from the cache.

#### `class Memory(capacity: int = 20, keep: int = 10, episodes: list[tuple[float, str]]=<factory>, summary: str = '')`

Episodes `(time, text)` and a summary of the ones folded away.

**Variables:**

- **capacity** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – episodes kept verbatim before the oldest are summarised.
- **keep** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – episodes left verbatim after a summary.
- **episodes** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*float*](https://docs.python.org/3/builtins/functions.html#float)*, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]**]*) – the verbatim episodes, oldest first.
- **summary** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the summary of everything older.

#### `add(time: float, text: str) → None`

Record one episode.

#### `property full: bool`

Whether the oldest episodes should be summarised.

#### `older() → str`

The current summary and the episodes the next summary folds away, as text.

#### `fold(summary: str) → None`

Replace the older episodes with `summary`; the newest `keep` stay.

#### `context() → str`

What the agent remembers, as the start of a prompt; empty when nothing.

#### `class MemoryAgent`

An `LLMAgent` whose calls start with its memory.

**Variables:**

**memory_keep** (*memory_capacity**,*) – the sizes of each agent’s `Memory`.

Example

```default
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
```

#### `property memory: Memory`

This agent’s memory, made on first use.

#### `remember(text: str) → None`

Record an episode at the model’s time; summarise when the memory is full.

#### `summarise() → None`

Fold the older episodes into a summary written by the model.

#### `llm_request(prompt: str, *, schema: dict[str, Any] | None = None, **params: Any) → Request`

A request whose prompt starts with what the agent remembers.

Planning, reflection and tool use for language-model agents.

- `plan(agent, goal)`: the agent writes a plan of a few steps, as a JSON list, and remembers it when it has a memory.
- `reflect(agent)`: the agent reads its memory and writes what it has learned, which it remembers: the reflection loop of generative agents.
- `use_tools(agent, prompt, tools)`: the agent may call functions of the model (look up a price, check its stock) before it answers. Each round it replies with a tool and its arguments or with its answer; a tool’s result is sent back in the same conversation, and after `max_rounds` tool calls it must answer.

Every call goes through the agent’s client, cached and counted like any other, so a run with plans, reflections and tool calls replays from its cache.

**Reference:**

Park, J. S., O’Brien, J. C., Cai, C. J., Morris, M. R., Liang, P. and Bernstein, M. S. (2023). Generative agents: interactive simulacra of human behavior. UIST 2023.

#### `plan(agent: Any, goal: str, max_steps: int = 5) → list[str]`

The agent’s plan toward `goal`: at most `max_steps` steps.

#### `reflect(agent: Any, question: str = 'What have you learned so far?') → str`

The agent’s reflection on its memory, remembered.

#### `class Tool(name: str, description: str, function: ~collections.abc.Callable[[...], ~typing.Any], parameters: ~collections.abc.Mapping[str, str] = <factory>)`

A function the agent may call.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – how the agent calls it.
- **description** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – what it does, shown to the agent.
- **function** ([*collections.abc.Callable*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)*[**[**...**]**, **Any**]*) – `function(**arguments)`; its result is shown to the agent as JSON.
- **parameters** ([*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]*) – the names of its arguments and what each is.

#### `line() → str`

One line describing the tool to the agent.

#### `class ToolUse(answer: ~typing.Any, calls: list[tuple[str, dict[str, ~typing.Any], ~typing.Any]] = <factory>)`

The answer, and every tool call made on the way: `(name, arguments, result)`.

#### `use_tools(agent: Any, prompt: str, tools: Sequence[Tool], max_rounds: int = 3, repairs: int = 1) → ToolUse`

Let `agent` call `tools` before answering `prompt`.

**Raises:**

[**DecisionError**](https://remipelloux.github.io/Modelly/dev/apis/llm.html#modelly.llm.DecisionError) – when it still calls a tool after `max_rounds` calls.

Conversations between language-model agents, turn by turn, many at once.

`converse_many(groups, topic, turns)` runs one conversation per group of agents. In each turn every group’s next speaker is asked, with the transcript so far, and all groups’ calls of that turn are sent together, so 250 pairs of traders talk in `turns` rounds of concurrent calls rather than 500 one after another. Speakers take turns in order (`"round-robin"`) or are drawn from a generator (`order=rng`, never the same agent twice in a row), the model’s own, so a run is a function of its seed. After the conversation every participant that has a memory remembers it.

Each call carries the speaker’s scope and call counter, as every agent call does, so a conversation replays from the cache.

#### `class Turn(speaker: int, text: str, time: float)`

One utterance: who spoke (unique id), what, and the model’s time.

#### `converse_many(groups: Sequence[Sequence[Any]], topic: str, turns: int, *, order: Any = 'round-robin') → list[list[Turn]]`

One conversation per group; the transcripts, in the order of `groups`.

**Parameters:**

- **groups** – lists of `LLMAgent` instances of one model, two or more each.
- **topic** – what they talk about.
- **turns** – utterances per conversation.
- **order** – `"round-robin"`, or a `numpy` generator to draw each next speaker.

#### `converse(agents: Sequence[Any], topic: str, turns: int, *, order: Any = 'round-robin') → list[Turn]`

One conversation among `agents`: its transcript.

An evaluation harness for language-model agents: behaviour, consistency and cost.

`evaluate(build, clients, seeds=..., steps=..., metrics=...)` runs the same model with each client (a provider, a hosted model, a local one) on each seed, and records per run every behaviour metric (a function of the finished model), the calls sent and served from the cache, the tokens and the cost. `Evaluation.report()` gives per client the mean and spread of each metric over the seeds, how consistently its agents chose the same thing from one seed to the next (`choices`), and the totals of calls, tokens and cost: which model behaves as the study needs, how stably, and at what price.

#### `agreement(choices: Sequence[Sequence[Any]]) → float`

The share of positions where two seeds’ choices agree, over every pair of seeds.

#### `class Evaluation(runs: DataFrame, choices: Mapping[str, list[list[Any]]], metrics: tuple[str, ...])`

Every run’s metrics and usage, and the choices recorded for consistency.

**Variables:**

- **runs** (*pandas.DataFrame*) – one row per (client, seed).
- **choices** ([*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[**Any**]**]**]*) – per client, one list of choices per seed (empty without `choices`).
- **metrics** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – the names of the behaviour metrics.

#### `report() → DataFrame`

Per client: each metric’s mean and sd, the agreement, and the usage totals.

#### `evaluate(build: Callable[[int, Any], Any], clients: Mapping[str, Callable[[], Any]], *, seeds: Sequence[int], steps: int, metrics: Mapping[str, Callable[[Any], float]], choices: Callable[[Any], Sequence[Any]] | None = None) → Evaluation`

Run `build(seed, client)` for `steps` steps with every client on every seed.

`clients` maps a name to a function making a fresh `Client`, so runs share no cache unless the factory gives them one. `choices(model)` lists the agents’ decisions, in a fixed order, for the agreement between seeds.

A conversational market: traders who talk, ask a price, and buy or walk away.

Half the traders sell one crate a round at a cost of their own; the other half buy one if the price is below their value. Each round the model pairs every seller with a buyer, the pair talks for two turns (`converse_many`), the seller states an asking price and the buyer accepts or refuses (`decide_all`), and both remember the round (`MemoryAgent`). Every call goes through `model.llm`.

`local_trader` is an offline stand-in for a language model: it reads the trader’s value from its persona and answers in character (a seller asks a fifth above its cost, a buyer accepts a price at or below its value), so the market runs, caches and replays with no network and no key. Swap it for a real provider to study what a language model does.

#### `local_trader(request: Request) → str`

An offline trader: in character, from the value in its persona.

#### `class Trader(model: Market, value: float, seller: bool)`

A buyer or a seller of crates, with a value and a memory of its rounds.

A trader of value `value` (a seller’s cost, a buyer’s willingness to pay).

#### `property traded`

Column(int64, default=0)

#### `property value`

Column(float64, default=0.0)

#### `property seller`

Column(bool, default=False)

#### `class Market(traders: int = 500, rng: int = 0, client: Client | None = None)`

Sellers and buyers who talk, then trade; every call goes through `self.llm`.

**Variables:**

**prices** – the price of every trade, in order.

`traders` traders, half of each side, values drawn from `rng`.

#### `pairs() → list[tuple[Trader, Trader]]`

Every seller with a buyer, both sides shuffled by the model’s generator.

#### `step() → None`

Talk, ask, decide, remember.

#### `mean_price() → float`

The mean price of the trades so far (NaN before any).
