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
.venv/bin/python -m pytest -q --ignore=tests/visualization --ignore=tests/examples
bash scripts/audit-pelloux.sh
```

`tests/visualization` and `tests/examples` need the optional `viz` extra
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
