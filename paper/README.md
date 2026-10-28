# The Modelly paper (arXiv)

*Modelly: Fast and Reproducible Agent-Based Modelling in Python, with Calibration and
Sensitivity Analysis Built In.*

A paper for researchers deciding whether to use Modelly: what it is, why it is fast, how its
results are checked, and for which studies it is (and is not yet) the right tool. Every number
in it comes from a file or a script in this repository.

## Layout

| Path | What |
|---|---|
| `main.tex` | The paper; `\input`s the sections in order |
| `sections/` | Abstract, introduction, related work (with the feature comparison), design, research workflow, performance (speed-ups and the agreement study), correctness and reproducibility, what release 1.4 adds, use cases, threats and limitations, conclusion and availability, appendix (reproduction, workloads, intervals, release comparisons, further agreement tables, release 1.4 in detail, every comparison) |
| `references.bib` | Bibliography (BibTeX, `plainnat`) |
| `tables/playbooks.tex` | Results table, **generated** from `benchmarks/playbooks/results/*.json` |
| `figures/speedups.pdf` | Speed-up figure, **generated** from the same results (PNG preview alongside) |
| `data/agreement_small.json` | Raw summary statistics of the agreement study: 100 seeds, the Mesa 2.3 reference and every Modelly variant of every playbook |
| `data/gpu_speedup.json`, `data/weak_*.json` | Copies of the GPU comparison (`benchmarks/playbooks/results/`) and the weak-scaling runs (`benchmarks/distributed/results/`) behind Section 7 |
| `tables/agreement_small.tex`, `figures/agreement_small.pdf` | Agreement table and figure, **generated** from that data |
| `scripts/make_figures.py` | Regenerates the playbook table and the speed-up figure |
| `scripts/bootstrap_ci.py` | Paired bootstrap 95% intervals of every step-time speed-up (appendix table) |
| `scripts/ports.py` | Times the public ports against Mesa 2.3 and Mesa 3.5 and compares the Mesa 3.5 ports in distribution |
| `scripts/mesa_examples_table.py` | Table of Mesa's own examples against their codemod ports |
| `scripts/frames_threads.py` | Times mesa-frames with one polars thread and with all of them |
| `scripts/agreement.py`, `scripts/agreement_tables.py` | Run the agreement study (`run`) and regenerate its tables and figure (`analyse`) |
| `scripts/recovery.py` | Runs the ABC-SMC coverage study and regenerates its table |
| `scripts/release_gates_table.py` | Table of every release comparison from `data/release_gates.json` (part of `make figures`) |
| `scripts/ishigami.py` | Sobol indices of the Ishigami function as quoted (`data/ishigami.json`) |
| `scripts/assimilation.py` | The nowcasting tutorial's numbers as quoted (`data/assimilation.json`) |
| `scripts/package_arxiv.py` | Checks the sources without LaTeX; packs the arXiv archive |
| `Makefile` | `make`, `make figures`, `make check`, `make arxiv`, `make clean` |

## Build

```bash
make figures      # needs the repository's .venv (matplotlib)
make              # needs TeX Live or MiKTeX with latexmk (or: tectonic main.tex)
make check        # no LaTeX needed: inputs, figures, citations, references, environments
make arxiv        # writes modelly-arxiv.tar.gz, including main.bbl
```

No TeX distribution? Upload the folder to Overleaf (it compiles `main.tex` with BibTeX as is).

## Where the numbers come from

| Claim | Source | Regenerate with |
|---|---|---|
| Playbook speed-ups, build and step times, determinism (Table 3, Figure 1) | `benchmarks/playbooks/results/*.json` | `benchmarks/playbooks/compare.py`, then `make figures` |
| Agreement with Mesa: 100 seeds at the small size (Table 5, Figure 2), 50 at the timed size (Table 6) | `data/agreement_small.json`, `data/agreement_large.json` | `scripts/agreement.py run --size small` (or `large`), then `analyse` |
| Port bit-identical, CPU time ratios (Section 5.1) | the private medfly harness (`benchmarks/mesaVSmodelly/paired.py`, not in the repository) | paired runs of the plain codemod port against the unmodified Mesa notebook |
| 1.3.2 against 1.3.1 and 1.3.3 against 1.3.2 (Section 5.4) | `data/release_gates.json` | `python -m modelly.dev perf --against <previous>`, the paired playbook and notebook runs |
| 1.3.1 against 1.2.0 (Section 5.4) | `docs/performance.md`, "No regression from release to release" | `python -m modelly.dev perf --against 1.2.0`, the playbook runner |
| Ishigami indices (Section 6.2) | `tests/sensitivity`, `docs/sensitivity.md` | `pytest tests/sensitivity` |
| ABC-SMC coverage over 200 datasets per model (Table 8) | `data/recovery.json` | `scripts/recovery.py run`, then `analyse` |
| Every agreement comparison (appendix G) | `data/agreement_small_summary.json` | `scripts/agreement.py analyse` |
| Grid epidemic at the timed size, 200 seeds (Section 5.3) | `data/agreement_large_grid200.json` | `scripts/agreement.py run --size large --seeds 200 --playbooks grid_epidemic --tag large_grid200` |
| Mesa 3.5 and mesa-frames against Mesa 2.3, 100 seeds (Section 5.3) | `data/agreement_small_baselines.json` | `scripts/agreement.py run --variants mesa3 frames --tag small_baselines` |
| Schelling over 300 seeds, every implementation (Section 5.3) | `data/agreement_schelling300.json` | `scripts/agreement.py run --seeds 300 --playbooks schelling --variants mesa3 frames modelly modelly-cells --tag schelling300` |
| Same code: two public ports against Mesa 2.3 and five against Mesa 3.5, with the Mesa 3.5 ports' agreement over 100 seeds (Section 5.1) | `data/port_public.json`, `benchmarks/ports/`, `benchmarks/ports_mesa3/` | `scripts/ports.py --rounds 10 --core 2` |
| Bootstrap intervals of the speed-ups (appendix) | `benchmarks/playbooks/results/*.json` | `scripts/bootstrap_ci.py` (part of `make figures`) |
| Mesa 3.5 + numpy against Mesa 2.3, 100 seeds (Section 5.2, appendix) | `data/agreement_small_mesa3np.json` | `scripts/agreement.py run --variants mesa3np --playbooks grid_epidemic schelling boltzmann_wealth --tag small_mesa3np` |
| Mesa 3.5 + numpy grid epidemic at the timed size, 100 seeds (Section 5.2) | `data/agreement_large_grid_mesa3np.json` | `scripts/agreement.py run --size large --playbooks grid_epidemic --variants mesa3np --tag large_grid_mesa3np` |
| Mesa's own examples against their codemod ports: timing and agreement (Section 5.1) | `data/mesa_examples.json`, `benchmarks/mesa_examples/` | `benchmarks/mesa_examples/run.py --rounds 10 --seeds 100 --core 2 --agree-cores 8-15`, then `scripts/mesa_examples_table.py` |
| mesa-frames with one thread and with all (Section 5.2) | `data/frames_threads.json` | `scripts/frames_threads.py` |
| Workload parameters (appendix B) | `benchmarks/playbooks/registry.py` | `make figures` |
| Determinism (Section 6.1, Table 7) | `tests/determinism`, `tests/determinism/golden.json` | `pytest tests/determinism` |
| Split runs equal one process; MPI 2 and 4 ranks (Section 7, Appendix F.1) | `tests/distributed/`, `tests/determinism/test_determinism_partition.py` | `pytest tests/distributed tests/determinism/test_determinism_partition.py` (needs mpi4py for the MPI cases) |
| Weak scaling (Table 18) | `data/weak_mpi_10k.json`, `data/weak_mpi_40k.json`, `data/weak_dask_10k.json` | `benchmarks/distributed/weak_scaling.py` |
| GPU speed-up and equality at 10 million agents (Section 7, Appendix F.2) | `data/gpu_speedup.json` | `benchmarks/playbooks/gpu_speedup.py` in a CUDA environment (`docs/gpu.md`) |
| Differentiable recoveries and gradient checks (Section 7, Appendix F.3) | `tests/diff/`, `docs/differentiable.md` | `pytest tests/diff` (needs jax) |
| Event heap, column gather, 1.4 against 1.3.3, memory-mapped 100 M rows, PGO (Section 7, Appendix F.4) | `docs/performance.md` | `modelly bench --against 1.3.3`, `benchmarks/large_columns.py`, `benchmarks/pgo.py` |
| Nowcasting error and EnKF recovery (Section 7, Appendix F.5) | `docs/assimilation.md` run by `tests/stream/test_assimilation_tutorial.py` | `pytest tests/stream` |
| Field numerics and the two coupled zoo models (Section 7, Appendix F.6) | `tests/couple/`, `tests/zoo/test_nutrient_foragers.py`, `test_hospital_epidemic.py` | `pytest tests/couple tests/zoo` |
| History-matching volumes and active learning against LHS (Section 7, Appendix F.7) | `docs/emulators.md`, `tests/emulate/` | `pytest tests/emulate`; `benchmarks/emulate/active_vs_lhs.py` |
| Synthetic population and the real-data zoo models (Section 7, Appendix F.8) | `tests/population/test_sample_region.py`, `tests/zoo/`, `modelly/space/geo/data/NOTICE.md` | `pytest tests/population tests/zoo` |
| Browser runs and first load (Section 7, Appendix F.9) | `docs/browser.md` | `MODELLY_BROWSER_TESTS=1 pytest tests/web/test_browser.py`; `tools/web/measure_load.py` |
| NetLogo fire percolation threshold (Section 6.2) | `docs/netlogo.md` | `pytest tests/netlogo` |
| Nowcasting error, resamplings and EnKF recovery as quoted (Section 7, Appendix F.5) | `data/assimilation.json` | `scripts/assimilation.py` |
| Ishigami estimates as quoted (Section 6.2) | `data/ishigami.json` | `scripts/ishigami.py` |
| Every release comparison (Table 13) | `data/release_gates.json` | `scripts/release_gates_table.py` (part of `make figures`) |
| 105 GPU and differentiable tests on CuPy and CUDA JAX (Appendix F.3) | `tests/gpu`, `tests/diff` in the GPU environment (`docs/gpu.md`) | `pytest tests/gpu tests/diff` in `.gpu-venv` |
| Feature comparison (Table 1) | each project's documentation and repository, October 2026 | by hand: check again before submitting |

If the benchmark results are rerun (for a new release, or on different hardware), run
`make figures` and update the hardware line at the start of Section 5.

## Before submitting

- [x] Author e-mail in `main.tex`.
- [x] Author affiliation in `main.tex` (OpenPro).
- [x] Every entry of `references.bib` with a DOI checked against Crossref (authors, title,
      venue, volume, issue, pages, year); the two JASSS articles without DOI and the mesa-frames
      URL checked to resolve.
- [x] Table 1 re-checked against each project's documentation and repository (October 2026).
- [x] ABC-SMC weight correction released as 1.3.2 and the codemod fix as 1.3.3; the paper
      describes 1.4.0.
- [ ] Release 1.4.0 tagged after the fixed-frequency gate against 1.3.3; replace the sentence
      marked `% GATE-1.4.0` in `sections/performance.tex` with its numbers and add them to
      `data/release_gates.json`.
- [ ] The five zoo models added after the browser run (Section 7, Appendix F.9) run from
      their export in the local release checks (`scripts/release-checks.sh browser`); update
      the "26 of 31" count in `sections/release14.tex` and `sections/appendix_release14.tex`.
- [ ] Recount the tests and the strictly typed files at the tag (the sentence marked
      `% COUNTS-1.4.0` in `sections/availability.tex`).
- [ ] For a journal: Appendix G (every comparison of the agreement study) becomes a CSV
      supplement generated from `data/agreement_small_summary.json`; Appendix F is the
      supplementary material for Section 7.
- [ ] Software Heritage archives the release commit; update the SWHID marked `% SWHID-1.4.0`
      in `sections/availability.tex`.
- [x] Compiled (Tectonic, no warnings); every page read.
- [x] All timings re-run at a fixed frequency (performance governor, turbo off, CPU 2).
- [x] Mesa 3.5 timed on all eight playbooks, mesa-frames on four, a hand-vectorised Mesa 3.5
      (numpy) baseline on three (Table 3, Figure 1).
- [ ] Optional, for a journal: ask Mesa and mesa-frames maintainers to review the baselines,
      and report the three mesa-frames defects upstream.
- [x] A public same-code result on Mesa's own examples: eight of ten port (Table 2).
- [ ] Decide whether to name the medfly model of Section 5.1 and cite its authors.
- [ ] arXiv categories: primary **cs.MA** (Multiagent Systems); cross-list **cs.MS**
      (Mathematical Software) and, depending on the audience, **physics.soc-ph** or
      **q-bio.PE**. A first submission to cs.MA may need an endorsement.
- [ ] Licence for the arXiv record (for example CC BY 4.0).
- [x] For a journal: software-availability, funding, competing-interest and data-availability
      declarations (Declarations, after Section 11).
- [x] Commit and push `paper/`; the repository is archived by Software Heritage (SWHID in
      Appendix A).
- [ ] Optional: archive the exact version on Zenodo (`modelly bundle`) and cite its DOI in
      Section 11 (Availability).
