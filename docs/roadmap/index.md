# Roadmap

**Status:** 1.3 released, 1.4.0 in progress (S1) · **Current release:** 1.3.3

Four releases take Modelly from a fast agent-based modelling framework to the research platform
people use to **build, calibrate, explain, scale, share and publish** a model, in any field, on
**Windows, macOS and Linux alike**.

| Release | Theme | One line |
|---|---|---|
| [1.3.0](1.3.0.md) | Answers and trust | Calibrate, explain and publish a model: experiments, calibration, sensitivity, provenance, Studio, model zoo |
| [1.4.0](1.4.0.md) | Scale out and connect | Distributed and GPU runs, differentiable models, live data and digital twins, Modelly in the browser |
| [1.5.0](1.5.0.md) | Ecosystem and collaboration | Model hub, model cards, policy and causal tools, LLM agents II, R and Julia bindings |
| [2.0.0](2.0.0.md) | Clean foundations | One space API, one clock, columns by default, typed scenarios, stable ABI and checkpoint format |

Every feature on these pages must work on Windows, macOS and Linux before it ships. How that is
guaranteed, and the support matrix for each release, is on [Platforms](platforms.md).

## Order, not dates

The roadmap has no dates. The releases ship in order (1.3.0, 1.4.0, 1.5.0, 2.0.0) because each
one stands on the one before, as the diagram below shows. Inside a release, work is split into
eight sprints: a sprint is a unit of work with exit criteria, not a period of time, and the next
sprint starts as soon as the previous one's criteria hold. Each release has three public
pre-releases (alpha, beta, release candidate), each behind a gate of checks, not a calendar.

## How the releases build on each other

```{mermaid}
flowchart LR
    subgraph R13["1.3.0 Answers and trust"]
        X[Experiments and executors]
        C[Calibration and sensitivity]
        P[Provenance and bundles]
        S[Studio]
        Z[Model zoo]
    end
    subgraph R14["1.4.0 Scale out and connect"]
        D[Distributed runs]
        G[GPU and differentiable models]
        W[Modelly in the browser]
        L[Live data and assimilation]
    end
    subgraph R15["1.5.0 Ecosystem and collaboration"]
        H[Model hub and model cards]
        K[Policy and causal tools]
        B[R and Julia bindings]
    end
    subgraph R20["2.0.0 Clean foundations"]
        U[One space API, one clock]
        A[Stable ABI and formats]
    end
    X --> D
    C --> G
    C --> L
    S --> W
    P --> H
    Z --> H
    C --> K
    D --> U
    G --> U
    H --> A
```

## What every release promises

- **Backward compatibility within 1.x.** A model written for 1.2 runs on 1.5. What changes is
  deprecated with a warning naming the replacement, and removed only in 2.0.
- **Reproducibility.** The same seed gives the same result, with the compiled modules or their
  pure-Python twins, on every supported platform. Each release widens what "the same" covers.
- **Cross-platform.** Windows, macOS and Linux are first-class: same features, same results,
  wheels for each. See [Platforms](platforms.md).
- **Discipline.** Every change follows `pelloux-guidelines.md`: files at most 300 lines,
  function bodies at most 25 lines, the local gate green, docs building with warnings as errors.

## Who it is for

The roadmap is written for researchers in many fields, not one: epidemiology and public health,
ecology and conservation, economics and finance, sociology and political science, urban studies
and transport, energy and climate, archaeology and anthropology, computational social science
with language models, teaching, and the research software engineers who support them. Each
release page says which of them each feature serves.

## How this roadmap is maintained

- The roadmap is a plan, not a promise: scope moves as we learn. Changes are made in
  pull requests against `docs/roadmap/` and noted in the release page's review log.
- At the end of each sprint the release page gets a review entry: what shipped, what slipped and
  why, and the `modelly bench` summary.
- Proposals and questions are welcome as GitHub issues labelled `roadmap`.

```{toctree}
:maxdepth: 1

1.3.0 <1.3.0>
1.4.0 <1.4.0>
1.5.0 <1.5.0>
2.0.0 <2.0.0>
Platforms <platforms>
```
