# Build the Modelly paper.  Needs a TeX distribution (TeX Live or MiKTeX) with latexmk;
# the figure needs the repository's Python environment (matplotlib).
#
#   make            figures, then main.pdf
#   make figures    regenerate figures/ and tables/ from the benchmark results
#   make check      check the sources without LaTeX
#   make arxiv      main.pdf, then modelly-arxiv.tar.gz for upload (includes main.bbl)
#   make clean

PYTHON ?= ../.venv/bin/python

.PHONY: all figures check arxiv clean

all: figures main.pdf

figures:
	$(PYTHON) scripts/make_figures.py
	$(PYTHON) scripts/bootstrap_ci.py

main.pdf: main.tex sections/*.tex references.bib figures/speedups.pdf tables/playbooks.tex
	latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

check:
	$(PYTHON) scripts/package_arxiv.py

arxiv: all
	$(PYTHON) scripts/package_arxiv.py --pack

clean:
	latexmk -C main.tex
	rm -f modelly-arxiv.tar.gz
