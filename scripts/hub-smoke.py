"""Release smoke test of the hub: install a zoo model from the public index and run it.

Run by the release workflow on every operating system the wheels are built for, with the
installed wheel: the public index is read over HTTPS, ``within_host`` is installed into a
temporary folder and run for a few days, and every zoo model card must be complete and
validated on the source in the wheel.

    python scripts/hub-smoke.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    """Install, run, check; the exit status."""
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "outbreak"
        hub = [
            sys.executable,
            "-m",
            "modelly",
            "hub",
            "install",
            "within_host",
            str(target),
        ]
        subprocess.run(hub, check=True)
        run = (
            "import model; m = model.WithinHost(model.WithinHostScenario(rng=1, hosts=500, "
            "days=10)); m.run(); assert m.attack_rate() > 0"
        )
        subprocess.run([sys.executable, "-c", run], cwd=target, check=True)
    cards = [sys.executable, "-m", "modelly", "card", "check", "--zoo"]
    subprocess.run(cards, check=True)
    sys.stdout.write("hub smoke test passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
