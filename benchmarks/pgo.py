"""Profile-guided optimisation of the compiled modules with GCC, measured against -O3.

    python benchmarks/pgo.py OUT_DIR [--rounds 7] [--core 3]

Copies the ``modelly`` package twice into OUT_DIR (``plain/`` and ``pgo/``), compiles
the C modules into ``plain`` with the build's flags (-O3) and into ``pgo`` in three
steps: with -fprofile-generate, then ``benchmarks/pgo_training.py`` runs on them, then
again with -fprofile-use. It then times every Modelly playbook variant at size large
in the two trees, paired and alternating as ``modelly bench --against`` does, and
prints that report (results must be identical). Run it with Modelly's dependencies
installed and GCC as the interpreter's compiler; with Clang (llvm-profdata merge) or
MSVC (/GL, /LTCG:PGINSTRUMENT) the steps differ and are not implemented here.

docs/performance.md records the result: no playbook was measurably faster, so the
build (hatch_build.py) does not use a profile.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hatch_build import NATIVE_DIR, OPTIMISE, SOURCES  # noqa: E402
from modelly.bench import against  # noqa: E402
from modelly.bench.pinning import choose  # noqa: E402
from modelly.bench.playbooks import load_registry, select_variants  # noqa: E402

TRAINING = ROOT / "benchmarks" / "pgo_training.py"
GCC_BANNER = "Free Software Foundation"  # in ``gcc --version``, not in clang's
GENERATE = ("-fprofile-generate={}", "-fprofile-update=single")
USE = ("-fprofile-use={}", "-fprofile-correction", "-Wno-missing-profile")
IGNORED = shutil.ignore_patterns("*.so", "*.pyd", "__pycache__")


def compile_module(source: Path, out_dir: Path, extra: tuple[str, ...]) -> Path:
    """Compile one module as hatch_build does, plus ``extra`` flags."""
    ldshared = shlex.split(sysconfig.get_config_var("LDSHARED"))
    out = out_dir / f"{source.stem}{sysconfig.get_config_var('EXT_SUFFIX')}"
    include = f"-I{sysconfig.get_paths()['include']}"
    cmd = [*ldshared, *OPTIMISE, *extra, include, str(ROOT / source), "-o", str(out)]
    subprocess.run(cmd, check=True)
    return out


def is_gcc() -> bool:
    """Whether the interpreter's compiler (the first word of LDSHARED) is GCC."""
    compiler = shlex.split(sysconfig.get_config_var("LDSHARED") or "cc")[0]
    done = subprocess.run(
        [compiler, "--version"], capture_output=True, text=True, check=False
    )
    return GCC_BANNER in done.stdout


def build(out: Path) -> None:
    """The plain tree, then the instrumented, trained and profiled one."""
    for tree in ("plain", "pgo"):
        shutil.rmtree(out / tree, ignore_errors=True)
        shutil.copytree(ROOT / "modelly", out / tree / "modelly", ignore=IGNORED)
    for source in SOURCES:
        compile_module(source, out / "plain" / NATIVE_DIR, ())
    profile = Path(tempfile.mkdtemp(prefix="modelly-pgo-"))
    native = out / "pgo" / NATIVE_DIR
    for (
        source
    ) in SOURCES:  # same output paths in both steps: GCC names profiles after them
        compile_module(source, native, tuple(f.format(profile) for f in GENERATE))
    env = {**os.environ, "PYTHONPATH": str(out / "pgo")}
    env.pop("MODELLY_PURE_PYTHON", None)
    subprocess.run([sys.executable, str(TRAINING)], env=env, check=True)
    for source in SOURCES:
        compile_module(source, native, tuple(f.format(profile) for f in USE))


def compare(out: Path, rounds: int, core: int | None) -> str:
    """Every Modelly playbook variant, plain against profiled, paired."""
    base = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "MODELLY_PURE_PYTHON"}
    }
    sides = against.Sides(
        "-O3",
        sys.executable,
        {**base, "PYTHONPATH": str(out / "plain")},
        {**base, "PYTHONPATH": str(out / "pgo")},
    )
    playbooks = ROOT / "benchmarks" / "playbooks"
    args = argparse.Namespace(
        playbooks=playbooks, rounds=rounds, seed=1, size="large", threshold=0.03
    )
    variants = select_variants(load_registry(playbooks), [], "large")
    pinning = choose(core)
    pairings = against.pair_rounds(args, variants, pinning, sides)
    return against.text(pairings, sides, args, pinning).replace("checkout", "PGO")


def main(argv: list[str]) -> int:
    """Build both trees and print the comparison."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--core", type=int, default=None)
    args = parser.parse_args(argv)
    if not is_gcc():
        sys.stderr.write("pgo.py: the interpreter's compiler is not GCC\n")
        return 1
    build(args.out)
    sys.stdout.write(compare(args.out, args.rounds, args.core) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
