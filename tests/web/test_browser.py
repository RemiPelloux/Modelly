"""Every example and zoo model runs in a headless Chromium from its static export.

Opt-in, because each page downloads Pyodide (about 15 MB, from its CDN) and starts a
browser: ``MODELLY_BROWSER_TESTS=1 pytest tests/web/test_browser.py``. The CI job
``browser`` in ``.github/workflows/build_lint.yml`` runs it. Each model is exported with
``export_web``, served by a local static server and opened in one browser context (so the
Pyodide files are downloaded once); the test runs ``STEPS`` steps and checks the page
reports no error. With ``MODELLY_WASM_WHEEL=path/to/modelly_abm-...-wasm32.whl`` (from
``scripts/build-wasm-wheel.sh``) every model runs once more with that wheel, and the page
must report the four compiled modules.
"""

import functools
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from modelly.web.export import WebExport, export_web
from modelly.web.runtime import NATIVE_MODULES
from modelly.zoo import MODELS

pytestmark = pytest.mark.skipif(
    os.environ.get("MODELLY_BROWSER_TESTS") != "1",
    reason="browser tests are opt-in: set MODELLY_BROWSER_TESTS=1",
)
sync_api = pytest.importorskip("playwright.sync_api")

STEPS = 10
EXPORT_STEPS = 2
LOAD_TIMEOUT_MS = 180_000
RUN_TIMEOUT_MS = 300_000
EXAMPLES = (
    "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth",
    "modelly.examples.basic.boid_flockers.model:BoidFlockers",
    "modelly.examples.basic.conways_game_of_life.model:ConwaysGameOfLife",
    "modelly.examples.basic.schelling.model:Schelling",
    "modelly.examples.basic.virus_on_network.model:VirusOnNetwork",
    "modelly.examples.advanced.alliance_formation.model:MultiLevelAllianceModel",
    "modelly.examples.advanced.epstein_civil_violence.model:EpsteinCivilViolence",
    "modelly.examples.advanced.pd_grid.model:PdGrid",
    "modelly.examples.advanced.sugarscape_g1mt.model:SugarscapeG1mt",
    "modelly.examples.advanced.wolf_sheep.model:WolfSheep",
    "modelly.examples.behaviour.tram_model.model:TransitSystem",
    "modelly.examples.llm.llm_opinions.model:LLMOpinions",
    "modelly.examples.spatial.commuting_city.model:CommutingCity",
    "modelly.examples.spatial.layered_epidemic.model:LayeredEpidemic",
)
ZOO = tuple(f"{model.module}:{model.model}" for model in MODELS)
WASM_WHEEL = os.environ.get("MODELLY_WASM_WHEEL")
WHEELS = (None, Path(WASM_WHEEL)) if WASM_WHEEL else (None,)


class QuietHandler(SimpleHTTPRequestHandler):
    """A static file handler that does not log each request."""

    def log_message(self, *args):
        """Say nothing."""


@pytest.fixture(scope="module")
def site_root(tmp_path_factory):
    """The folder the static server serves; each test exports into it."""
    return tmp_path_factory.mktemp("sites")


@pytest.fixture(scope="module")
def server(site_root):
    """A static server for ``site_root`` on a free local port; its URL."""
    handler = functools.partial(QuietHandler, directory=str(site_root))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()
    thread.join()


@pytest.fixture(scope="module")
def browser_context():
    """One headless Chromium context, so the Pyodide files are cached across pages."""
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        opened = browser.new_context()
        yield opened
        opened.close()
        browser.close()


def run_page(page, url: str) -> None:
    """Open ``url``, wait for Python, run STEPS steps and wait for the run to end."""
    page.goto(url)
    page.wait_for_selector(
        "body[data-state=ready], body[data-state=error]", timeout=LOAD_TIMEOUT_MS
    )
    assert page.get_attribute("body", "data-state") == "ready", page.inner_text(
        "#status"
    )
    page.fill("#steps", str(STEPS))
    page.click("#run")
    page.wait_for_selector("body:not([data-state=running])", timeout=RUN_TIMEOUT_MS)


@pytest.mark.parametrize("wheel", WHEELS, ids=lambda w: "wasm" if w else "pure")
@pytest.mark.parametrize("target", EXAMPLES + ZOO, ids=lambda t: t.rpartition(":")[2])
def test_model_runs_in_the_browser(target, wheel, site_root, server, browser_context):
    """The exported page loads, runs STEPS steps (or until the model stops), no error."""
    name = f"{target.rpartition(':')[2]}-{'wasm' if wheel else 'pure'}"
    export_web(WebExport(target, site_root / name, steps=EXPORT_STEPS, wheel=wheel))
    page = browser_context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        run_page(page, f"{server}/{name}/index.html")
        body = {
            key: page.get_attribute("body", f"data-{key}")
            for key in ("state", "steps", "running")
        }
        versions = page.inner_text("#versions")
    finally:
        page.close()
    assert body["state"] == "ready", body
    assert body["steps"] == str(STEPS) or body["running"] == "false", body
    assert not errors
    expected = f"compiled: {', '.join(NATIVE_MODULES)}" if wheel else "pure Python"
    assert expected in versions
