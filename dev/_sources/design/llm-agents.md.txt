# Design review: language-model agents (E7)

**Scope:** the client, providers, the response cache, budgets, structured decisions and how
LLM runs stay reproducible. **Code:** `modelly.llm`. **Guide:**
[Language-model agents](../llm_agents.md).

## Decisions

| Question | Decision | Alternatives considered | Why |
|---|---|---|---|
| How agents call a model | Every call goes through one `Client` (`model.llm` by convention); agents mix in `LLMAgent` and call `decide(prompt, schema)` | Agents call provider SDKs directly; a framework such as LangChain | One choke point is where caching, budgets, retries, concurrency and the ordering of replies are enforced; lint rule MDL012 flags network calls that bypass it |
| Providers | Adapters over the standard library's HTTP: Anthropic's Messages API, OpenAI-compatible endpoints (OpenAI, Ollama, llama.cpp), and a `FakeProvider` for tests and teaching | Depend on each vendor's SDK | No provider is needed to install Modelly, the same code reaches local models, and the adapters are small enough to audit |
| Reproducibility | A deterministic response cache keyed on the SHA-256 of provider, model, prompts, parameters, the model's seed, the calling agent and its own call counter | Rely on temperature 0; seed the provider | Hosted models are not deterministic and may be retired; recording what was said is the only way to replay a run, and per-agent counters make keys independent of thread timing |
| The store | SQLite from the standard library, rollback journal, one transaction per reply; exports as sorted JSON lines (plain or gzip with a zero timestamp) or SQLite | A JSON file; a key-value server | Crash-safe and dependency-free; the sorted text export is diffable and gives the same bytes for the same calls |
| Modes | `read-write` (record what is missing), `read-only` (replay: a miss raises `CacheMiss`, nothing is sent), `off` | Always read-write | A reviewer must be able to prove that a replay made no call |
| Budgets | Token and cost budgets reserved before each call (prompt estimate plus `max_tokens`); no bundled prices | Count after the fact; ship a price table | A budget must stop a run before it overspends; prices change and a stale one is worse than none |
| Structured decisions | JSON Schema validation of replies, with a bounded number of repair calls | Free text parsed by the model code | Decisions that feed a model's state must be typed; repairs are calls too, so they are cached and counted |
| Checkpoints and bundles | The client, its cache and counters are part of the model's checkpoint; from 1.4 `modelly run` exports the replies next to the outputs and `modelly bundle` packs them, and `modelly verify` replays them | Leave the cache to the user | "The bundle verifies with no network" was a done-when of E7 that 1.3 left to the user; 1.4 closes it |

## What 1.4 added

- `modelly.llm.replay.replaying(path)`: inside the block every `Client` created answers only
  from the recorded replies, read-only, whatever provider and cache the model builds. `modelly
  verify` reruns under it, so a study that called a hosted model verifies offline and without
  an API key (`tests/provenance/test_provenance_llm.py` refuses every socket while it checks).

## Known limits

- A replay reproduces a run only when the run asks the same questions in the same order; a
  changed prompt changes its key and stops the replay at the first unrecorded call.
- The cache records a model's answers, not the model: a replay cannot say what a newer model
  would have answered.
