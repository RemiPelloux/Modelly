"""Measure the first load of an exported site: bytes transferred and time until it runs.

    python tools/web/measure_load.py SITE_DIR [--profile fast-4g] [--runs 3]

The site (``modelly export-web ... --out SITE_DIR``) is served from 127.0.0.1 and opened
in a fresh headless Chromium context per run, with the HTTP cache off and the network
throttled through the DevTools protocol, so every run is a cold first visit. The clock
starts at navigation and stops when the page reports ``data-state=ready`` with the model
built (Pyodide, packages, Modelly and the model loaded, step 0 drawn). Transfer sizes are
the encoded (on the wire, compressed) body and header bytes Playwright reports for every
request, the Web Worker's included. Pyodide comes
from its CDN, so the real network adds its own latency on top of the emulated one.
"""

from __future__ import annotations

import argparse
import functools
import json
import statistics
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

MBIT = 1_000_000 / 8  # bytes per second in one megabit per second
# Chrome DevTools' presets (front_end/core/sdk/NetworkManager.ts), and a broadband line.
PROFILES = {
    "fast-4g": {
        "download": 9 * MBIT * 0.9,
        "upload": 1.5 * MBIT * 0.9,
        "latency": 60 * 2.75,
    },
    "slow-4g": {
        "download": 1.6 * MBIT * 0.9,
        "upload": 0.75 * MBIT * 0.9,
        "latency": 150 * 3.75,
    },
    "broadband-50": {"download": 50 * MBIT, "upload": 10 * MBIT, "latency": 40},
    "none": None,
}
READY = "body[data-state=ready][data-steps='0'], body[data-state=error]"
TIMEOUT_MS = 300_000


class QuietHandler(SimpleHTTPRequestHandler):
    """A static file handler that does not log each request."""

    def log_message(self, *args):
        """Say nothing."""


def serve(folder: Path) -> tuple[ThreadingHTTPServer, str]:
    """A static server for ``folder`` on a free port, and its URL."""
    handler = functools.partial(QuietHandler, directory=str(folder))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/index.html"


def one_run(browser, url: str, profile: dict | None) -> dict:
    """One cold load: seconds to ready and encoded bytes by host."""
    context = browser.new_context()
    page = context.new_page()
    cdp = context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    if profile:
        conditions = {"offline": False, "latency": profile["latency"]}
        conditions |= {
            "downloadThroughput": profile["download"],
            "uploadThroughput": profile["upload"],
        }
        cdp.send("Network.emulateNetworkConditions", conditions)
    finished = []

    def record(request):
        """Keep a finished request (Playwright cannot wrap a built-in method)."""
        finished.append(request)

    # Playwright reports the Web Worker's requests too (the Pyodide downloads).
    context.on("requestfinished", record)
    start = time.perf_counter()
    page.goto(url)
    page.wait_for_selector(READY, timeout=TIMEOUT_MS)
    seconds = time.perf_counter() - start
    state = page.get_attribute("body", "data-state")
    by_host: dict[str, int] = {}
    for request in finished:
        host = urlparse(request.url).netloc
        sizes = request.sizes()
        size = sizes["responseBodySize"] + sizes["responseHeadersSize"]
        by_host[host] = by_host.get(host, 0) + size
    context.close()
    return {"seconds": round(seconds, 2), "state": state, "bytes": by_host}


def main(argv: list[str] | None = None) -> int:
    """Measure ``--runs`` cold loads and print them, with the median, as JSON."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("site", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="fast-4g")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args(argv)
    httpd, url = serve(args.site)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            runs = [
                one_run(browser, url, PROFILES[args.profile]) for _ in range(args.runs)
            ]
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    report = {
        "site": str(args.site),
        "profile": args.profile,
        "conditions": PROFILES[args.profile],
        "median_seconds": statistics.median(r["seconds"] for r in runs),
        "median_bytes": statistics.median(sum(r["bytes"].values()) for r in runs),
        "runs": runs,
    }
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0 if all(r["state"] == "ready" for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
