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
| `sections/` | Abstract, introduction, related work (with the feature comparison), design, research workflow, performance (speed-ups and the agreement study), correctness and reproducibility, threats to validity, use cases and limitations, availability and conclusion, appendix |
| `references.bib` | Bibliography (BibTeX, `plainnat`) |
| `tables/playbooks.tex` | Results table, **generated** from `benchmarks/playbooks/results/*.json` |
| `figures/speedups.pdf` | Speed-up figure, **generated** from the same results (PNG preview alongside) |
| `data/agreement_small.json` | Raw summary statistics of the agreement study: 100 seeds, the Mesa 2.3 reference and every Modelly variant of every playbook |
| `tables/agreement_small.tex`, `figures/agreement_small.pdf` | Agreement table and figure, **generated** from that data |
| `scripts/make_figures.py` | Regenerates the playbook table and the speed-up figure |
| `scripts/bootstrap_ci.py` | Paired bootstrap 95% intervals of every step-time speed-up (appendix table) |
| `scripts/ports.py` | Times the public ports against Mesa 2.3 and Mesa 3.5 and compares the Mesa 3.5 ports in distribution |
| `scripts/frames_threads.py` | Times mesa-frames with one polars thread and with all of them |
| `scripts/agreement.py`, `scripts/agreement_tables.py` | Run the agreement study (`run`) and regenerate its tables and figure (`analyse`) |
| `scripts/recovery.py` | Runs the ABC-SMC coverage study and regenerates its table |
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
| Playbook speed-ups, build and step times, determinism (Table 2, Figure 1) | `benchmarks/playbooks/results/*.json` | `benchmarks/playbooks/compare.py`, then `make figures` |
| Agreement with Mesa: 100 seeds at the small size (Table 3, Figure 2), 50 at the timed size (Table 4) | `data/agreement_small.json`, `data/agreement_large.json` | `scripts/agreement.py run --size small` (or `large`), then `analyse` |
| Port bit-identical, CPU time ratios (Section 5.1) | the private medfly harness (`benchmarks/mesaVSmodelly/paired.py`, not in the repository) | paired runs of the plain codemod port against the unmodified Mesa notebook |
| 1.3.1 against 1.2.0 (Section 5.4) | `docs/performance.md`, "No regression from release to release" | `python -m modelly.dev perf --against 1.2.0`, the playbook runner |
| Ishigami indices (Section 6.2) | `tests/sensitivity`, `docs/sensitivity.md` | `pytest tests/sensitivity` |
| ABC-SMC coverage over 200 datasets per model (Table 6) | `data/recovery.json` | `scripts/recovery.py run`, then `analyse` |
| Every agreement comparison (appendix D) | `data/agreement_small_summary.json` | `scripts/agreement.py analyse` |
| Grid epidemic at the timed size, 200 seeds (Section 5.3) | `data/agreement_large_grid200.json` | `scripts/agreement.py run --size large --seeds 200 --playbooks grid_epidemic --tag large_grid200` |
| Mesa 3.5 and mesa-frames against Mesa 2.3, 100 seeds (Section 5.3) | `data/agreement_small_baselines.json` | `scripts/agreement.py run --variants mesa3 frames --tag small_baselines` |
| Schelling over 300 seeds, every implementation (Section 5.3) | `data/agreement_schelling300.json` | `scripts/agreement.py run --seeds 300 --playbooks schelling --variants mesa3 frames modelly modelly-cells --tag schelling300` |
| Same code: two public ports against Mesa 2.3 and five against Mesa 3.5, with the Mesa 3.5 ports' agreement over 100 seeds (Section 5.1) | `data/port_public.json`, `benchmarks/ports/`, `benchmarks/ports_mesa3/` | `scripts/ports.py --rounds 10 --core 2` |
| Bootstrap intervals of the speed-ups (appendix) | `benchmarks/playbooks/results/*.json` | `scripts/bootstrap_ci.py` (part of `make figures`) |
| Mesa 3.5 + numpy against Mesa 2.3, 100 seeds (Section 5.2, appendix) | `data/agreement_small_mesa3np.json` | `scripts/agreement.py run --variants mesa3np --playbooks grid_epidemic schelling boltzmann_wealth --tag small_mesa3np` |
| Mesa 3.5 + numpy grid epidemic at the timed size, 100 seeds (Section 5.2) | `data/agreement_large_grid_mesa3np.json` | `scripts/agreement.py run --size large --playbooks grid_epidemic --variants mesa3np --tag large_grid_mesa3np` |
| mesa-frames with one thread and with all (Section 5.2) | `data/frames_threads.json` | `scripts/frames_threads.py` |
| Workload parameters (appendix B) | `benchmarks/playbooks/registry.py` | `make figures` |
| Determinism (Section 6.1, Table 5) | `tests/determinism`, `tests/determinism/golden.json` | `pytest tests/determinism` |
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
- [x] ABC-SMC weight correction released as 1.3.2; the paper describes 1.3.2.
- [x] Compiled (Tectonic, no warnings beyond one underfull caption line); every page read.
- [x] Mesa 3.5 timed on all eight playbooks, mesa-frames on four, a hand-vectorised Mesa 3.5
      (numpy) baseline on three (Table 2, Figure 1).
- [ ] Optional, for a journal: ask Mesa and mesa-frames maintainers to review the baselines,
      and report the three mesa-frames defects upstream.
- [ ] Recommended: a public same-code result (the codemod applied to Mesa's own example
      models, timed unchanged), since the medfly notebook cannot be distributed.
- [ ] Decide whether to name the medfly model of Section 5.1 and cite its authors.
- [ ] arXiv categories: primary **cs.MA** (Multiagent Systems); cross-list **cs.MS**
      (Mathematical Software) and, depending on the audience, **physics.soc-ph** or
      **q-bio.PE**. A first submission to cs.MA may need an endorsement.
- [ ] Licence for the arXiv record (for example CC BY 4.0).
- [ ] For a journal (JASSS, EMS, SoftwareX): a software-availability block and the funding,
      competing-interest, data-availability and generative-AI declarations. Section 8 already
      states that the playbook implementations were written with AI coding assistants.
- [ ] Commit and push `paper/`, and archive that commit (Zenodo DOI): Section 10 and appendix A
      say the data and scripts are in the repository.
- [ ] Optional: archive the exact version on Zenodo (`modelly bundle`) and cite its DOI in
      Section 10 (Availability).
