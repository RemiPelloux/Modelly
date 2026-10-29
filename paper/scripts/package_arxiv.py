r"""Check the paper's sources and pack them for arXiv.

    python paper/scripts/package_arxiv.py           # check only
    python paper/scripts/package_arxiv.py --pack    # check, then write paper/modelly-arxiv.tar.gz

The check needs no LaTeX installation: every \input and \includegraphics target exists,
every \cite key is in references.bib, every \cref target has a \label, and every
\begin has its \end. The archive holds what arXiv compiles: main.tex, the sections, the
generated table and figure, references.bib and, when present, main.bbl (arXiv does not run
BibTeX on uploads that include a .bbl; build it once with ``make`` first).
"""

from __future__ import annotations

import io
import re
import sys
import tarfile
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ARCHIVE = PAPER / "modelly-arxiv.tar.gz"
GRAPHIC_SUFFIXES = (".pdf", ".png")
PATTERNS = {
    "input": re.compile(r"\\input\{([^}]+)\}"),
    "graphic": re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}"),
    "cite": re.compile(r"\\cite[pt]?\{([^}]+)\}"),
    "ref": re.compile(r"\\[cC]ref\{([^}]+)\}"),
    "label": re.compile(
        r"\\label\{([^}]+)\}|\blabel=\{([^}]+)\}"
    ),  # \\label, listings' label=
    "begin": re.compile(r"\\begin\{([^}]+)\}"),
    "end": re.compile(r"\\end\{([^}]+)\}"),
}


def sources() -> dict[Path, str]:
    """main.tex and every file it inputs, by path."""
    found, pending = {}, [PAPER / "main.tex"]
    while pending:
        path = pending.pop()
        if not path.exists():
            continue  # reported by problems()
        text = path.read_text(encoding="utf-8")
        found[path] = text
        for name in PATTERNS["input"].findall(text):
            target = PAPER / (name if name.endswith(".tex") else f"{name}.tex")
            if target not in found:
                pending.append(target)
    return found


def problems(texts: dict[Path, str]) -> list[str]:
    """Everything that would break the build or the references."""
    allx = "\n".join(texts.values())
    bib = (PAPER / "references.bib").read_text(encoding="utf-8")
    keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    labels = {a or b for a, b in PATTERNS["label"].findall(allx)}
    issues = [
        f"missing input {n}"
        for n in PATTERNS["input"].findall(allx)
        if not (PAPER / (n if n.endswith(".tex") else f"{n}.tex")).exists()
    ]
    issues += [
        f"missing figure {g}"
        for g in PATTERNS["graphic"].findall(allx)
        if not any((PAPER / f"{g}{s}").exists() for s in ("", *GRAPHIC_SUFFIXES))
    ]
    cited = {
        k.strip() for group in PATTERNS["cite"].findall(allx) for k in group.split(",")
    }
    issues += [f"citation not in references.bib: {k}" for k in sorted(cited - keys)]
    issues += reference_problems(allx, labels)
    issues += [
        f"unbalanced environments in {path.relative_to(PAPER)}"
        for path, text in texts.items()
        if not balanced(text)
    ]
    return issues


def reference_problems(allx: str, labels: set[str]) -> list[str]:
    r"""\cref targets without a label, and targets LaTeX cannot resolve: with whitespace."""
    groups = PATTERNS["ref"].findall(allx)
    spaced = sorted({r for group in groups for r in group.split(",") if r != r.strip()})
    refs = {r.strip() for group in groups for r in group.split(",")}
    return [
        f"reference with whitespace, which LaTeX cannot resolve: {r!r}" for r in spaced
    ] + [f"reference without a label: {r}" for r in sorted(refs - labels)]


def balanced(text: str) -> bool:
    r"""Whether every \begin{x} is closed by its own \end{x}, in order."""
    stack = []
    for match in re.finditer(r"\\(begin|end)\{([^}]+)\}", text):
        kind, name = match.groups()
        if kind == "begin":
            stack.append(name)
        elif not stack or stack.pop() != name:
            return False
    return not stack


# arXiv builds with pdfLaTeX and asks for this in the first lines; Tectonic (XeTeX) fails on it.
ARXIV_FIRST_LINE = "\\pdfoutput=1\n"


def add_text(archive: tarfile.TarFile, name: str, text: str) -> None:
    """Add ``text`` to ``archive`` as the file ``name``."""
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def pack(texts: dict[Path, str]) -> Path:
    """The arXiv archive of the sources, the generated assets and the bibliography."""
    used = "\n".join(texts.values())
    figures = [
        PAPER / f"{g}.pdf" for g in sorted(set(PATTERNS["graphic"].findall(used)))
    ]
    files = [*texts, PAPER / "references.bib", *figures]
    if (PAPER / "main.bbl").exists():
        files.append(PAPER / "main.bbl")
    with tarfile.open(ARCHIVE, "w:gz") as archive:
        for path in files:
            if path.name == "main.tex":
                add_text(
                    archive,
                    "main.tex",
                    ARXIV_FIRST_LINE + path.read_text(encoding="utf-8"),
                )
            else:
                archive.add(path, arcname=str(path.relative_to(PAPER)))
    return ARCHIVE


def main(argv: list[str]) -> int:
    """Check, and pack with --pack; exit 1 when the check fails."""
    texts = sources()
    issues = problems(texts)
    for issue in issues:
        print(issue)
    if issues:
        return 1
    print(
        f"{len(texts)} source files: inputs, figures, citations, references and environments check"
    )
    if "--pack" in argv:
        print(f"wrote {pack(texts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
