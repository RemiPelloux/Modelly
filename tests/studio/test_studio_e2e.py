"""End to end: ``modelly studio`` serves a page a headless Chromium can drive.

The server runs as a subprocess on a free port, as a user would start it; the test
clicks Step and Run, and checks the browser asked for nothing outside localhost.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("solara")
sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[2]
TARGET = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
START_TIMEOUT_S = 60
POLL_S = 0.2
PAGE_TIMEOUT_MS = 60_000
LOCAL_PREFIXES = ("http://127.0.0.1", "ws://127.0.0.1", "data:", "blob:")


def free_port() -> int:
    """A port the OS reports as free."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def wait_until_up(url: str, process: subprocess.Popen) -> None:
    """Poll ``url`` until the server answers."""
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"modelly studio exited with {process.returncode}")
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except OSError:
            time.sleep(POLL_S)
    pytest.fail(f"modelly studio did not answer on {url}")


@pytest.fixture
def studio_url():
    """A running ``modelly studio`` for Boltzmann wealth; its URL."""
    port = free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    command = [sys.executable, "-m", "modelly", "studio", TARGET]
    command += ["--port", str(port), "--no-browser"]
    process = subprocess.Popen(command, cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    try:
        wait_until_up(url, process)
        yield url
    finally:
        process.terminate()
        process.wait(timeout=START_TIMEOUT_S)


def test_the_page_runs_the_model(studio_url):
    """Load the page, step and run the model, open the profiler tab."""
    requests = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except sync_api.Error as error:
            pytest.skip(f"no Chromium for playwright: {error}")
        page = browser.new_page()
        page.on("request", lambda request: requests.append(request.url))
        page.goto(studio_url)
        page.get_by_text("Timeline").wait_for(timeout=PAGE_TIMEOUT_MS)
        page.get_by_role("button", name="Step").click()
        page.get_by_text("step 1", exact=True).wait_for(timeout=PAGE_TIMEOUT_MS)
        page.get_by_role("button", name="Run 10").click()
        page.get_by_text("step 11", exact=True).wait_for(timeout=PAGE_TIMEOUT_MS)
        page.get_by_role("tab", name="Profiler").click()
        page.get_by_text("11 step(s) profiled").wait_for(timeout=PAGE_TIMEOUT_MS)
        browser.close()
    assert [url for url in requests if not url.startswith(LOCAL_PREFIXES)] == []
