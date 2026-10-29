"""Does every Python listing of the paper run as printed? A check.

    python paper/scripts/check_listings.py

Extracts every ``lstlisting`` block of the sections that is Python (the bash block of the
appendix is skipped), writes each to a scratch directory and runs it there with this
interpreter. The ABC listing imports ``epidemic``, the model module of
``docs/calibration.md``; the check writes that module from the documentation's own code
blocks (the model, then the observed series ``cases``), so the listing runs against the
documented module as the caption says. Prints one line per listing and exits non-zero
when one fails.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
BLOCK = re.compile(
    r"\\begin\{lstlisting\}(\[(?P<options>(?:[^\[\]]|\[[^\]]*\])*)\])?\n(?P<code>.*?)\\end\{lstlisting\}",
    re.DOTALL,
)
FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)
TIMEOUT = 600


def listings() -> list[tuple[str, str]]:
    """(label, code) of every Python listing in the sections, in order."""
    out = []
    for path in sorted((PAPER / "sections").glob("*.tex")):
        for match in BLOCK.finditer(path.read_text(encoding="utf-8")):
            options = match.group("options") or ""
            if "language=bash" in options:
                continue
            label = re.search(r"label=\{([^}]*)\}", options)
            out.append((label.group(1) if label else path.stem, match.group("code")))
    return out


def epidemic_module() -> str:
    """docs/calibration.md's model module with its observed series, as one file."""
    blocks = FENCE.findall(
        (ROOT / "docs" / "calibration.md").read_text(encoding="utf-8")
    )
    model = blocks[0]
    series = blocks[1].split("calibration = ABCSMC(")[0]
    series = "\n".join(
        line for line in series.splitlines() if not line.startswith("from ")
    )
    return model + "\n\n" + series + "\n"


def main() -> int:
    """Write, run and report every listing."""
    scratch = Path(tempfile.mkdtemp(prefix="modelly-paper-listings-"))
    (scratch / "epidemic.py").write_text(epidemic_module(), encoding="utf-8")
    failures = []
    for label, code in listings():
        script = scratch / f"{label.replace(':', '_')}.py"
        script.write_text(code, encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, script.name],
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                check=False,
            )
            ok, detail = completed.returncode == 0, completed.stderr[-600:]
        except subprocess.TimeoutExpired:
            ok, detail = False, f"no result within {TIMEOUT} s"
        print(f"{'ran    ' if ok else 'FAILED '} {label}")
        if ok and completed.stdout.strip():
            print("    " + completed.stdout.strip().replace("\n", "\n    ")[:800])
        if not ok:
            failures.append(f"{label}: {detail}")
    if failures:
        print("\n" + "\n".join(failures))
        return 1
    print("\nevery Python listing runs as printed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
