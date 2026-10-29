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
| `sections/` | Abstract, introduction, related work (with the feature comparison), design, research workflow, performance (speed-ups and the agreement study), correctness and reproducibility, scaling out and connecting to data, use cases, threats and limitations, conclusion and availability, appendix (reproduction, workloads, intervals, further agreement tables, scaling out in detail, every comparison) |
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
| `scripts/ishigami.py` | Sobol indices of the Ishigami function as quoted (`data/ishigami.json`) |
| `scripts/assimilation.py` | The nowcasting tutorial's numbers as quoted (`data/assimilation.json`) |
| `scripts/graph_cut.py` | The graph partitioner's edge cut on a 30 x 30 lattice (`data/graph_cut.json`) |
| `scripts/environment.py` | The commit, date and package versions the three scripts above record |
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
| Ishigami indices (Section 6.2) | `tests/sensitivity`, `docs/sensitivity.md` | `pytest tests/sensitivity` |
| ABC-SMC coverage over 200 datasets per model (Table 8) | `data/recovery.json` | `scripts/recovery.py run`, then `analyse` |
| Every agreement comparison (appendix F) | `data/agreement_small_summary.json` | `scripts/agreement.py analyse` |
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
| Split runs equal one process; MPI 2 and 4 ranks (Section 7, Appendix E.1) | `tests/distributed/`, `tests/determinism/test_determinism_partition.py` | `pytest tests/distributed tests/determinism/test_determinism_partition.py` (needs mpi4py for the MPI cases) |
| Weak scaling (Table 17) | `data/weak_mpi_10k.json`, `data/weak_mpi_40k.json`, `data/weak_dask_10k.json` | `benchmarks/distributed/weak_scaling.py` |
| GPU speed-up and equality at 10 million agents (Section 7, Appendix E.2) | `data/gpu_speedup.json` | `benchmarks/playbooks/gpu_speedup.py` in a CUDA environment (`docs/gpu.md`) |
| Differentiable recoveries and gradient checks (Section 7, Appendix E.3) | `tests/diff/`, `docs/differentiable.md` | `pytest tests/diff` (needs jax) |
| Event heap, column gather, memory-mapped 100 M rows (Appendix E.4) | `tests/native/`, `build/logs` of the measurement run | `benchmarks/large_columns.py` under `systemd-run -p MemoryMax=16G` and `3G` |
| Nowcasting error and EnKF recovery (Section 7, Appendix E.5) | `docs/assimilation.md` run by `tests/stream/test_assimilation_tutorial.py` | `pytest tests/stream` |
| Field numerics and the two coupled zoo models (Section 7, Appendix E.6) | `tests/couple/`, `tests/zoo/test_nutrient_foragers.py`, `test_hospital_epidemic.py` | `pytest tests/couple tests/zoo` |
| History-matching volumes and active learning against LHS (Section 7, Appendix E.7) | `docs/emulators.md`, `tests/emulate/` | `pytest tests/emulate`; `benchmarks/emulate/active_vs_lhs.py` |
| Synthetic population and the real-data zoo models (Section 7, Appendix E.8) | `tests/population/test_sample_region.py`, `tests/zoo/`, `modelly/space/geo/data/NOTICE.md` | `pytest tests/population tests/zoo` |
| Browser runs (62 of 62: 14 examples and 17 zoo models, two wheels) and first load (Section 7, Appendix E.9) | `tests/web/test_browser.py` run by `scripts/release-checks.sh browser`; `docs/browser.md` | `MODELLY_BROWSER_TESTS=1 pytest tests/web/test_browser.py`; `tools/web/measure_load.py` |
| Graph partitioner's edge cut on a lattice (Appendix E.1) | `data/graph_cut.json` | `scripts/graph_cut.py` |
| Implementation choices, mesa-frames threads (Appendix B) | `docs/performance.md`, `data/frames_threads.json` | `scripts/frames_threads.py` |
| NetLogo fire percolation threshold (Section 6.2) | `docs/netlogo.md` | `pytest tests/netlogo` |
| Nowcasting error, resamplings and EnKF recovery as quoted (Section 7, Appendix E.5) | `data/assimilation.json` | `scripts/assimilation.py` |
| Ishigami estimates as quoted (Section 6.2) | `data/ishigami.json` | `scripts/ishigami.py` |
| 105 GPU and differentiable tests on CuPy and CUDA JAX (Appendix E.3) | `tests/gpu`, `tests/diff` in the GPU environment (`docs/gpu.md`) | `pytest tests/gpu tests/diff` in `.gpu-venv` |
| Feature comparison (Table 1) | each project's documentation and repository, October 2026 | by hand: check again before submitting |

If the benchmark results are rerun (on different hardware, say), run `make figures` and
update the hardware line at the start of Section 5.

## Before submitting

- [x] Author e-mail in `main.tex`.
- [x] Author affiliation in `main.tex` (OpenPro).
- [x] Every entry of `references.bib` with a DOI checked against Crossref (authors, title,
      venue, volume, issue, pages, year); the two JASSS articles without DOI and the mesa-frames
      URL checked to resolve.
- [x] Table 1 re-checked against each project's documentation and repository (October 2026).
- [x] The paper describes one version, 1.4.0, and compares Modelly only with other
      frameworks, never with its own earlier versions.
- [x] Every measurement re-run on the tagged release v1.4.0 (`build/release/measure_140.sh`:
      timings at the fixed frequency, GPU, weak scaling, agreement, coverage), `make figures`
      run and every number in the text refreshed from the new files. Not re-run on the tag: the
      browser's first-load times, the 100-million-row run and the PGO measurement, taken on the
      same code before the tag (Appendix E).
- [x] Every model, the five zoo models added last included, runs from its export in the
      local release checks (`scripts/release-checks.sh browser`, 62 of 62 with both wheels).
- [x] Tests and coverage counted at the tag's gate (3,038 tests, 2,980 pass, 58 skip; 97.3%).
- [ ] For a journal: Appendix F (every comparison of the agreement study) becomes a CSV
      supplement generated from `data/agreement_small_summary.json`; Appendix E is the
      supplementary material for Section 7.
- [ ] Software Heritage archives the tag v1.4.0; add its identifier at the comment marked `% SWHID-1.4.0`
      in `sections/appendix.tex` (Appendix A).
- [x] Compiled (Tectonic, no warnings); every page read.
- [x] All timings re-run at a fixed frequency (performance governor, turbo off, CPU 2).
- [x] Mesa 3.5 timed on all eight playbooks, mesa-frames on four, a hand-vectorised Mesa 3.5
      (numpy) baseline on three (Table 3, Figure 1).
- [ ] Optional, for a journal: ask Mesa and mesa-frames maintainers to review the baselines,
      and report the three mesa-frames defects upstream.
- [x] A public same-code result on Mesa's own examples: eight of ten port (Table 2).
- [ ] arXiv categories: primary **cs.MA** (Multiagent Systems); cross-list **cs.MS**
      (Mathematical Software) and, depending on the audience, **physics.soc-ph** or
      **q-bio.PE**. A first submission to cs.MA may need an endorsement.
- [ ] Licence for the arXiv record (for example CC BY 4.0).
- [x] For a journal: software-availability, funding, competing-interest and data-availability
      declarations (Declarations, after Section 11).
- [x] Commit and push `paper/`.
- [ ] Optional: archive the exact version on Zenodo (`modelly bundle`) and cite its DOI in
      Section 11 (Availability).
