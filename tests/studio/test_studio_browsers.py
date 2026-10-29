"""Studio in real browsers, opt-in: offline assets, the run controls, the WebGL map at scale.

Heavy: every test starts a ``modelly studio`` server and a headless browser, so the suite
runs only when ``MODELLY_BROWSER`` names one Playwright browser, one at a time::

    MODELLY_BROWSER=chromium pytest tests/studio/test_studio_browsers.py
    MODELLY_BROWSER=firefox pytest tests/studio/test_studio_browsers.py
    MODELLY_BROWSER=webkit pytest tests/studio/test_studio_browsers.py

WebKit stands in for Safari; Edge is Chromium. ``MODELLY_BROWSER_EXECUTABLE`` names a browser
binary of your own, for instance a wrapper around Playwright's WebKit that adds the Ubuntu
libraries a non-Ubuntu Linux lacks. The server serves Solara's front-end files
from a copy of the local cache, with the CDN pointed at a closed local port: a file
missing from the cache fails the page instead of being downloaded, so a passing run shows
Studio works offline.
"""

import io
import os
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager

import pytest

pytest.importorskip("solara")
sync_api = pytest.importorskip("playwright.sync_api")

from modelly.studio.assets import cache_folder  # noqa: E402
from tests.studio.test_studio_e2e import (  # noqa: E402
    LOCAL_PREFIXES,
    ROOT,
    START_TIMEOUT_S,
    free_port,
    wait_until_up,
)

BROWSER = os.environ.get("MODELLY_BROWSER", "")
# A browser binary of your own, e.g. a wrapper that adds libraries the OS lacks.
EXECUTABLE = os.environ.get("MODELLY_BROWSER_EXECUTABLE") or None
pytestmark = pytest.mark.skipif(
    not BROWSER, reason="set MODELLY_BROWSER=chromium, firefox or webkit to run"
)
BOLTZMANN = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
SWARM, WEB = "tests.studio.models:Swarm", "tests.studio.models:Web"
CLOSED_CDN = "http://127.0.0.1:9/npm/"  # the discard port: nothing listens
CDN_PATH = "/_solara/cdn/"
PAGE_TIMEOUT_MS = 120_000
HTTP_ERROR = 400
CANVAS = "canvas.modelly-map-canvas"
RENDERERS = ("webgl", "canvas2d")


@contextmanager
def studio(target: str, cache, *options: str):
    """A ``modelly studio`` on ``target`` serving Solara's files from ``cache`` only."""
    port = free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    env |= {
        "SOLARA_ASSETS_PROXY_CACHE_DIR": str(cache),
        "SOLARA_ASSETS_CDN": CLOSED_CDN,
    }
    command = [sys.executable, "-m", "modelly", "studio", target, *options]
    command += ["--port", str(port), "--no-browser"]
    process = subprocess.Popen(command, cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    try:
        wait_until_up(url, process)
        yield url
    finally:
        process.terminate()
        process.wait(timeout=START_TIMEOUT_S)


@pytest.fixture(scope="module")
def cache(tmp_path_factory):
    """A copy of this environment's Solara front-end cache."""
    folder = tmp_path_factory.mktemp("cdn")
    shutil.copytree(cache_folder(), folder, dirs_exist_ok=True)
    return folder


def in_browser(url: str, drive) -> dict:
    """Open ``url`` in ``BROWSER``, run ``drive(page, seen)``; what the page asked for.

    Runs in its own thread: the sync API refuses to run where pytest-playwright's
    asyncio loop runs.
    """
    seen = {"requests": [], "failed": [], "errors": []}

    def run() -> None:
        try:
            with sync_api.sync_playwright() as playwright:
                kind = getattr(playwright, BROWSER)
                browser = kind.launch(executable_path=EXECUTABLE)
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.on("request", lambda r: seen["requests"].append(r.url))
                page.on(
                    "response",
                    lambda r: r.status >= HTTP_ERROR and seen["failed"].append(r.url),
                )
                page.goto(url)
                page.get_by_text("Timeline").wait_for(timeout=PAGE_TIMEOUT_MS)
                drive(page, seen)
                browser.close()
        except Exception as error:  # re-raised in the test's thread
            seen["errors"].append(error)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if seen["errors"]:
        error = seen["errors"][0]
        if "Executable doesn't exist" in str(error) or "Host system is missing" in str(
            error
        ):
            pytest.skip(f"{BROWSER} cannot start here: {str(error).splitlines()[0]}")
        raise error
    return seen


def open_map(page, points: int) -> dict:
    """Open the Map tab and wait for ``points`` agents drawn; the canvas's report."""
    page.get_by_role("tab", name="Map").click()
    canvas = page.locator(f'{CANVAS}[data-points="{points}"]')
    canvas.wait_for(timeout=PAGE_TIMEOUT_MS)
    report = canvas.evaluate("c => ({...c.dataset})")
    report["image"] = canvas.screenshot()
    return report


def colours_in(png: bytes) -> int:
    """How many distinct colours a PNG screenshot holds."""
    from matplotlib.image import imread  # noqa: PLC0415

    pixels = imread(io.BytesIO(png))[..., :3].reshape(-1, 3)
    return len({tuple(p) for p in pixels[:: max(1, len(pixels) // 20_000)]})


def test_studio_runs_offline(cache):
    """Step, run, open the map: nothing beyond localhost, no front-end file missing."""
    found = {}

    def drive(page, seen):
        page.get_by_role("button", name="Step").click()
        page.get_by_text("step 1", exact=True).wait_for(timeout=PAGE_TIMEOUT_MS)
        page.get_by_role("button", name="Run 10").click()
        page.get_by_text("step 11", exact=True).wait_for(timeout=PAGE_TIMEOUT_MS)
        found.update(open_map(page, 100))

    with studio(BOLTZMANN, cache) as url:
        seen = in_browser(url, drive)
    assert [u for u in seen["requests"] if not u.startswith(LOCAL_PREFIXES)] == []
    assert [u for u in seen["failed"] if CDN_PATH in u] == []
    assert found["renderer"] in RENDERERS
    sys.stdout.write(f"{BROWSER}: map renderer {found['renderer']}\n")


def test_the_map_draws_100k_agents(cache):
    """100 000 agents drawn by WebGL (or Canvas 2D), then by Canvas 2D on request."""
    found = {}

    def drive(page, seen):
        found["webgl"] = open_map(page, 100_000)
        page.get_by_text("Canvas 2D instead of WebGL").click()
        selector = f'{CANVAS}[data-renderer="canvas2d"][data-points="100000"]'
        page.locator(selector).wait_for(timeout=PAGE_TIMEOUT_MS)
        found["canvas"] = page.locator(CANVAS).evaluate("c => ({...c.dataset})")

    with studio(SWARM, cache) as url:
        in_browser(url, drive)
    first = found["webgl"]
    assert first["renderer"] in RENDERERS
    assert colours_in(first["image"]) > 1  # agents on the white background
    assert found["canvas"]["renderer"] == "canvas2d"
    sys.stdout.write(
        f"{BROWSER}: 100k agents, {first['renderer']} {first['drawMs']} ms, "
        f"canvas2d {found['canvas']['drawMs']} ms\n"
    )


def test_the_map_draws_a_100k_edge_network(cache):
    """A 50 000-node network: its 100 000 edges and 25 000 agents."""
    found = {}

    def drive(page, seen):
        found.update(open_map(page, 25_000))

    with studio(WEB, cache) as url:
        in_browser(url, drive)
    assert found["segments"] == "100000"
    assert colours_in(found["image"]) > 1
    sys.stdout.write(
        f"{BROWSER}: 100k edges, {found['renderer']} {found['drawMs']} ms\n"
    )
