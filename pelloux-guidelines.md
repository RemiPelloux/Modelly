# Pelloux Guidelines — Modelly

Single source of truth for Modelly coding discipline, adapted from the
canonical Pelloux spec for a pure-Python package. The canonical numeric limits
and workflow principles below win over repo habit. Verify commands are
Modelly-specific (see §8).

---

## 1. Think Before Coding

- State assumptions explicitly. If uncertain, ask.
- Surface multiple interpretations — do not pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop and ask.

### Pick the simplest fix (mandatory for non-trivial work)

Before writing code, consider **at least three** plausible approaches (brief is fine):

1. **Fix at the failure point** — e.g. widen validation, one-line config, correct the bad assumption.
2. **Workaround elsewhere** — e.g. caller-side transform, extra keyword argument, adapter shim.
3. **New pipeline / abstraction** — new module, new base class, shared helper used once.

**Default to (1)** unless a lighter option cannot fully solve the request. If you choose (2) or (3), state in one sentence why (1) was rejected. Do not add caller-side complexity when a config change or a narrower fix suffices.

## 2. Simplicity First

- Minimum code that solves the problem. Nothing speculative.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that was not requested.
- No error handling for impossible scenarios.
- 200 lines that could be 50? Rewrite.

## 3. Surgical Changes

- Touch only what the task requires.
- Do not "improve" adjacent code unless asked.
- Match existing patterns in the repo.
- Pre-existing dead code → mention it; do not delete unless asked.
- Orphans created by your change → remove them.

Every changed line must trace directly to the request. Never run a whole-tree
formatter as a side effect of an unrelated change; if formatting is required,
scope it to the files you own.

## 4. Goal-Driven Execution

Turn work into verifiable steps before editing:

```
1. <step> → verify: <check>
2. <step> → verify: <check>
```

Bug fix → reproduce first (failing test), then verify fix.

## 5. Size and Shape Limits

| Scope | Target | Hard error |
|-------|--------|------------|
| General production file (`modelly/**`, examples exempt) | ≤ 300 lines | > 400 lines |
| Function / method body | ≤ 25 lines | warn in CI on new debt |
| Parameters (Python `def`) | ≤ 4 | use a dataclass / options object beyond |

- No magic numbers — use named constants or config.
- Prefer early returns to reduce nesting.

The audit allows 10 % slack on the file limits: it warns above 330 lines and
errors above 440. Function bodies are measured in source lines, docstring
excluded.

**Exemptions**: `tests/`, `docs/`, `benchmarks/`, `modelly/examples/`
(documentation-grade), generated notebooks, and anything listed in
`pelloux-baseline.json`. Legacy oversized files are recorded in
`pelloux-baseline.json`; they may shrink but never grow.

## 6. Code Hygiene

- No debug leftovers in commits (`print(`, `breakpoint()`, `pdb`, temporary
  `#` blocks). The audit treats `print(` and `breakpoint()` as errors
  everywhere in `modelly/` except `modelly/visualization/`, where console
  output is part of the feature and is reported as a warning instead.
- No commented-out code.
- No speculative abstractions (human review in definition-of-done).

## 7. Git Workflow

- Conventional Commits: `<type>(<scope>): <imperative subject ≤ 72 chars>`.
  Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`, `build`.
- One logical change per commit. Stage by explicit path, never `git add -A`
  (another agent may share the tree).
- Never push directly to `main`. `main` is the default and integration
  branch: branch from it, open a PR against it with a perfect conventional
  commit message, squash-merge, and delete the branch, remote and local.
- No attribution trailers (`Co-authored-by`, `Signed-off-by`) in commits.
- Never force-push shared branches.
- Preserve concurrent work: merge rather than overwrite.

## 8. Make / Test / Document

1. **Make** the feature (minimum scope).
2. **Test** it.
3. **Verify** static checks pass before commit.

Modelly verify commands. The gate is this computer, not a hosted runner:
`bash scripts/ci-local.sh` runs lint, format, the core test suite and the
Pelloux audit, free and offline, and reports each stage as passed or failed.

```sh
# Everything this machine can run (uses .venv/bin when present)
bash scripts/ci-local.sh
bash scripts/ci-local.sh --list             # stage names
bash scripts/ci-local.sh lint audit         # a subset of stages

# Individual checks
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q --ignore=tests/viz --ignore=tests/examples
bash scripts/audit-pelloux.sh
```

`tests/viz` and `tests/examples` need the optional `viz` extra
(solara); the local gate skips them and the hosted `build` workflow still runs
the full suite on push and PR.

Behavior changes need tests (happy + negative path). A feature is never closed
on the strength of its specification.

## 9. Enforcement

| Layer | Tool |
|-------|------|
| Local gate | `bash scripts/ci-local.sh` — the §8 commands, one stage per job, on this computer |
| Audit | `bash scripts/audit-pelloux.sh` (file limits against `pelloux-baseline.json`, debug leftovers, long-function warnings) |
| Baseline | `bash scripts/seed-pelloux-baseline.sh` — re-seed ONLY when a split or removal legitimately changes the recorded ceilings |
| Hosted runners | `.github/workflows/build_lint.yml` (pytest matrix, coverage, examples) runs on push and PR; it is a backstop, not the gate |

The audit does not certify runtime behavior or a release; it validates size,
shape and hygiene only.

## 10. Clean Dead Code

- Remove unused imports, methods, and variables your change created.
- Mention pre-existing issues; do not silently "fix" unrelated debt.

## 11. Python Rules for Modelly

These rules hold for every file under `modelly/` (examples excepted where noted).
The audit checks sizes; ruff checks style; the rules below are checked in review
and, where a test can pin them, by tests.

### 11.1 Layout and imports

- One domain per package: `core`, `space`, `time`, `data`, `behaviour`,
  `scenarios`, `batch`, `viz`, plus `_native`, `lint`. A new feature goes into
  the package of its domain; there is no `experimental` area.
- A domain package's `__init__.py` re-exports its public names and declares
  `__all__`. Inner sub-packages keep a docstring-only `__init__.py`.
- Inside `modelly/`, import from the **defining module**
  (`from modelly.space.cells.cell import Cell`), never from your own package's
  `__init__` and never `from modelly import X`: both depend on import order and
  break as soon as imports are re-sorted.
- Absolute imports only; no relative imports.
- Heavy or optional dependencies (`scipy`, `networkx`, `solara`, `matplotlib`,
  `altair`, `pyarrow`) are imported inside the function that needs them, with
  `# noqa: PLC0415` and the reason. `import modelly` must not load scipy
  (pinned by `tests/test_import_namespace.py`).
- Tests mirror the package layout: `tests/<domain>/test_<module>.py`.

### 11.2 Public API

- Public names have no leading underscore and a Google-style docstring
  (ruff `D`, convention `google`). Everything else is private.
- Public signatures change only in a major release. More than four parameters
  means a dataclass or a `Scenario` field, not another argument.
- Raise the specific exceptions of `modelly.core.exceptions` (or a subclass
  next to the feature). No bare `except:`; catch the narrowest exception.

### 11.3 Hot paths

Hot paths run once per agent or per cell per step: agent creation and removal,
agent-set loops (`do`, `shuffle_do`, `map`), cell moves, neighbourhood lookups,
event execution, signal emission, `DataCollector.collect`.

- No extra Python call inside the per-item loop. Validation, setup and rare
  branches go into helpers; the loop body stays inline. A hot function may
  exceed the 25-line body limit only when splitting it would add a per-item
  call; say so in a comment above it.
- Objects created per agent or per cell use `__slots__`.
- Prefer C-level operations (`dict`/`list` methods, comprehensions,
  `itertools`, numpy) over Python loops; never call through a subscripted
  generic (`CellCollection[Cell](...)`) on a hot path.
- No `contextlib.suppress` or `try/finally` wrappers per item: use
  `try/except` around the narrowest statement.

### 11.4 Determinism

- All randomness comes from the model: `model.random` (stdlib stream) or
  `model.rng` (numpy Generator). Never the global `random` or `np.random`.
- A performance change must not change the number, order or arguments of
  random draws, the iteration order of agent sets and cell collections, or the
  order of emitted signals and scheduled events. Results are bit-identical
  before and after, checked on every example model with several seeds.

### 11.5 Native code (`modelly/_native`)

- Every C function has a pure-Python twin with identical results, selected at
  import (`MODELLY_PURE_PYTHON=1` forces Python). The twin is the reference;
  the C version is a port of it.
- `tests/native/` runs both versions side by side on the same inputs,
  including edge cases (empty input, numpy integer arguments, mutation during
  the loop, exceptions) and checks reference counts after repeated calls.
- C code accepts what the Python twin accepts: use `PyNumber_AsSsize_t` (the
  `__index__` protocol, like `range()`), not `PyLong_AsSsize_t`.
- Every new `.c` file is listed in `SOURCES` in `hatch_build.py`.
- Move code to C only when a paired benchmark shows a gain at model level,
  not just in a micro-benchmark.

### 11.6 Measuring performance

- First check results are identical, then measure speed.
- Pair the measurements: alternate old and new in the same process (or in
  alternating processes on one pinned core) and compare CPU time
  (`time.thread_time`), not wall-clock on a busy machine.
- Report the median ratio with its spread and keep every round; a change
  inside the spread is noise, not a gain.
- Claims in docs and changelogs cite the workload, the machine load and the
  method.
