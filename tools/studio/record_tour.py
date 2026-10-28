"""Record the short Studio tour embedded in docs/studio.md, as a WebM video.

Starts ``modelly studio`` on the Wolf-Sheep example, drives it in headless Chromium with
Playwright's video recording (step, run, scrub back, the WebGL map, an ensemble) and writes
``docs/_static/studio/studio-tour.webm``. Run from the repository root, on any OS:

    python tools/studio/record_tour.py

The video is committed; rerun after changing Studio's layout. It stays under 3 MB.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "_static" / "studio" / "studio-tour.webm"
TARGET = "modelly.examples.advanced.wolf_sheep.model:WolfSheep"
SIZE = {"width": 1280, "height": 800}  # wide enough for the sidebar not to overlap
# The page is recorded scaled down: the file stays under 3 MB that way.
VIDEO = {"width": 960, "height": 600}
START_TIMEOUT_S = 60
WAIT_MS = 60_000
PAUSE_MS = 1200
SHORT_MS = 600


def free_port() -> int:
    """A port the OS reports as free."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def wait_until_up(url: str) -> None:
    """Poll ``url`` until the server answers."""
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except OSError:
            time.sleep(0.2)
    raise SystemExit(f"modelly studio did not answer on {url}")


def tour(page) -> None:
    """Step, run, scrub back to step 5, open the map, run an ensemble."""
    page.get_by_text("Timeline").wait_for(timeout=WAIT_MS)
    page.wait_for_timeout(PAUSE_MS)
    page.get_by_role("button", name="Step").click()
    page.get_by_text("step 1", exact=True).wait_for(timeout=WAIT_MS)
    page.get_by_role("button", name="Run 10").click()
    page.get_by_text("step 11", exact=True).wait_for(timeout=WAIT_MS)
    page.wait_for_timeout(PAUSE_MS)
    timeline = page.locator(".v-card", has_text="scrubbing restores").last
    slider = timeline.get_by_role("slider").first
    slider.focus()
    for _ in range(6):
        slider.press("ArrowLeft")
        page.wait_for_timeout(SHORT_MS // 2)
    page.wait_for_timeout(PAUSE_MS)
    back = page.get_by_role("button", name="Back to live")
    back.focus()  # the slider's label overlaps it in a narrow window
    back.press("Enter")
    page.get_by_role("tab", name="Map").click()
    page.locator("canvas.modelly-map-canvas[data-points]").wait_for(timeout=WAIT_MS)
    page.wait_for_timeout(PAUSE_MS)
    page.get_by_role("tab", name="Ensemble").click()
    page.get_by_role("button", name="Run ensemble").click()
    page.get_by_text("Bands (CSV)").wait_for(timeout=WAIT_MS)
    page.wait_for_timeout(2 * PAUSE_MS)


def record(url: str, folder: Path) -> Path:
    """Run the tour in Chromium, recording it; the video file."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport=SIZE, record_video_dir=str(folder), record_video_size=VIDEO
        )
        page = context.new_page()
        page.goto(url)
        tour(page)
        video = page.video
        context.close()
        browser.close()
        return Path(video.path())


def main() -> int:
    """Serve Studio, record the tour, stop the server; the exit status."""
    port = free_port()
    command = [sys.executable, "-m", "modelly", "studio", TARGET]
    command += ["--port", str(port), "--no-browser"]
    server = subprocess.Popen(command, cwd=ROOT)
    url = f"http://127.0.0.1:{port}"
    try:
        wait_until_up(url)
        with tempfile.TemporaryDirectory() as folder:
            video = record(url, Path(folder))
            OUT.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(video, OUT)
    finally:
        server.terminate()
        server.wait(timeout=START_TIMEOUT_S)
    sys.stdout.write(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 2**20:.2f} MiB\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
