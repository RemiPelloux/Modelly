"""A bundle made on this machine verifies in a fresh interpreter, from the command line."""

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
STEPS = "5"
SEED = "7"


def _modelly(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "modelly", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_bundle_verifies_in_a_fresh_subprocess(tmp_path):
    """Run, bundle, unpack elsewhere and verify with the CLI: the outputs match."""
    runs = tmp_path / "runs"
    ran = _modelly("run", TARGET, "--steps", STEPS, "--seed", SEED, "--out", str(runs))
    assert ran.returncode == 0, ran.stderr
    archive = tmp_path / "study.zip"
    packed = _modelly("bundle", str(runs), "--out", str(archive))
    assert packed.returncode == 0, packed.stderr
    review = tmp_path / "review"
    with zipfile.ZipFile(archive) as opened:
        opened.extractall(review)
    checked = _modelly("verify", str(review / "manifest.json"))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "outputs match" in checked.stdout
