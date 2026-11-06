# Where to publish

Checked on 2026-11-04. Fees and deadlines change: confirm on each venue's page before
submitting. Most journals refuse a manuscript under review elsewhere; a short software paper
(SoftwareX, JOSS) is a different article and can run alongside the full paper, if each cover
letter says so.

## Recommended order

1. **Preprints now.** arXiv (primary cs.MA, cross-list cs.MS; the endorsement request is in
   `endorsement_email.md`), with the Zenodo record giving the DOI (`zenodo_upload.py`), and
   OSF Preprints or TechRxiv if wanted (`METADATA.md`). Software Heritage archives the tag
   (Appendix A).
2. **The full paper to one journal.** JASSS first; Environmental Modelling & Software or ACM
   TOMACS as alternatives (see below).
3. **A short software paper.** SoftwareX now, or JOSS once the repository has six months of
   public history (from about late April 2027) and evidence of use by others. Choose one of
   the two: they describe the same software.
4. **Talks and short papers in 2027.** AAMAS demo track (deadline 27 December 2026), MABS,
   SciPy, the Social Simulation Conference, the Winter Simulation Conference; each needs its
   own shorter paper, not this manuscript.

## Journals

| Venue | Fit | Review | Cost to the author | Notes |
|---|---|---|---|---|
| [JASSS](https://www.jasss.org) | The ABM and social-simulation journal; takes framework and methods papers | Double-blind | None known (open access, no fee found; confirm) | Main text to about 25-30 pages, appendices as supplementary files |
| [Environmental Modelling & Software](https://www.sciencedirect.com/journal/environmental-modelling-and-software) | Good if framed around calibration and uncertainty for socio-ecological models | Single-blind | None (subscription route); open access about EUR 2,190 (2023 figure) | Long papers accepted |
| [ACM TOMACS](https://dl.acm.org/journal/tomacs) | Simulation methodology: determinism, equivalence testing, performance | Single-blind | Open access since 2026: USD 1,450, 950 for ACM members, waivers ([ACM](https://www.acm.org/articles/pubs-newsletter/2025/blue-diamond-july-2025)) | Slow (6 months or more) |
| [PeerJ Computer Science](https://peerj.com/computer-science/) | Software papers of any length, judged on soundness | Single-blind, optional open reviews | About USD 1,395-1,888 (unverified), waivers | 2-3 months |
| [Simulation Modelling Practice and Theory](https://www.sciencedirect.com/journal/simulation-modelling-practice-and-theory) | Performance and engineering | Single-blind | None (subscription); open access about USD 3,030 (unverified) | |
| [PLOS Computational Biology, Software](https://journals.plos.org/ploscompbiol/) | Only if reframed around epidemiology | Single-blind | USD 3,165 ([PLOS](https://plos.org/publish/fees/)) | Wants evidence of use in biology |
| [Journal of Open Research Software](https://openresearchsoftware.metajnl.com) | Short metapaper | | About GBP 350-400 | Mean 495 days to publication in 2025 ([JORS](https://openresearchsoftware.metajnl.com/about)): too slow |

## Short software papers

| Venue | Form | Cost | Eligibility |
|---|---|---|---|
| [SoftwareX](https://www.sciencedirect.com/journal/softwarex) | Original Software Publication, about 3,000 words and a code-metadata table | Open access, about USD 760-970 (unverified), waivers | No history requirement: possible now |
| [JOSS](https://joss.theoj.org) | `paper.md` of 750-1,750 words, no new results ([format](https://joss.readthedocs.io/en/latest/paper.html)) | Free | Six months of public development and evidence of research use ([submitting](https://joss.readthedocs.io/en/latest/submitting.html)): the repository and PyPI start on 2026-10-24, so not before about late April 2027 |
| [pyOpenSci](https://www.pyopensci.org) | Community package review | Free | Accepted packages can go on to JOSS with a lighter review |

## Conferences and talks

| Venue | Status on 2026-11-04 | Form |
|---|---|---|
| [AAMAS 2027 demo track](https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/call-for-demonstrations/) | Deadline 27 December 2026 (AoE); conference 5-7 May 2027, Hanoi, in person | Short demo paper in the proceedings |
| MABS 2027 (AAMAS workshop) | No call yet; the 2026 deadline was in February | Short paper, Springer LNAI |
| PyCon US 2027 | Call expected now, closing around mid-December | Talk |
| SciPy 2027 | No call yet; the 2026 deadline was 4 March | Talk and a free, openly reviewed proceedings paper with a DOI |
| Social Simulation Conference 2027 (ESSA) | No call yet; abstracts usually due in spring | Extended abstract |
| Winter Simulation Conference 2027 | No call yet; papers were due 5 April in 2026 | 12-page paper, agent-based track |
| EuroSciPy 2027 | No call yet | Talk or tutorial |

## Where to announce it

- CoMSES Net: list the framework and post on its forum (https://forum.comses.net).
- The SIMSOC mailing list; r/agentbasedmodeling and r/Python; Hacker News "Show HN" with a
  link to a browser export.
- Mesa's discussions only as a migration path for Mesa users (the codemod), not as a
  comparison.
- Indexing: Google Scholar picks up arXiv and Zenodo; link the arXiv record and the GitHub
  repository both ways.
