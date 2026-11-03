"""Accessibility audit (WCAG 2.0, 2.1 and 2.2, levels A and AA) with axe-core in Chromium.

Run by ``scripts/release-checks.sh a11y``: it serves a built documentation folder, starts
``modelly studio`` in English, in no-code French and right to left in Arabic, and runs
axe-core on each page. Any violation fails the stage and is printed with the elements it
names.

    python scripts/a11y-audit.py path/to/axe.min.js path/to/built/html
"""

from __future__ import annotations

import functools
import http.server
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

PAGES = ("index.html", "getting_started.html", "translations/fr/getting_started.html",
         "zoo/age_seir.html", "studio.html", "decide.html", "whats_new.html", "course/index.html")  # fmt: skip
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
TARGET = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
STUDIOS = ((), ("--language", "fr", "--no-code"), ("--language", "ar"))
START_TIMEOUT_S, PAGE_TIMEOUT_MS = 90, 90_000


def free_port() -> int:
    """A port nothing listens on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def violations(page, url: str, axe: str) -> list[str]:
    """axe-core's WCAG A and AA violations on ``url``, one line each."""
    page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
    page.add_script_tag(content=axe)
    result = page.evaluate(
        "t => axe.run(document, {runOnly: {type: 'tag', values: t}})", TAGS
    )
    return [f"{url}: [{v['impact']}] {v['id']}: {v['help']} {[n['target'] for n in v['nodes'][:3]]}"
            for v in result["violations"]]  # fmt: skip


def serve_docs(folder: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    """A static server of ``folder`` on a free port."""
    port = free_port()
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(folder)
    )
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def start_studio(options: tuple[str, ...]) -> tuple[subprocess.Popen, str]:
    """``modelly studio`` on a free port, once it answers."""
    port = free_port()
    command = [sys.executable, "-m", "modelly", "studio", TARGET, "--port", str(port), "--no-browser", *options]  # fmt: skip
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return process, url
        except OSError:
            time.sleep(0.2)
    process.terminate()
    raise RuntimeError(f"modelly studio {' '.join(options)} did not start")


def audit_studio(page, options: tuple[str, ...], axe: str) -> list[str]:
    """The violations of one Studio page, after it has drawn and run a step."""
    process, url = start_studio(options)
    try:
        page.goto(url, timeout=PAGE_TIMEOUT_MS)
        page.wait_for_selector(".v-btn", timeout=PAGE_TIMEOUT_MS)
        page.locator(".v-btn").first.click()
        time.sleep(2)
        page.add_script_tag(content=axe)
        result = page.evaluate(
            "t => axe.run(document, {runOnly: {type: 'tag', values: t}})", TAGS
        )
        return [f"studio {' '.join(options) or '(default)'}: [{v['impact']}] {v['id']}: {v['help']}"
                for v in result["violations"]]  # fmt: skip
    finally:
        process.terminate()
        process.wait(timeout=START_TIMEOUT_S)


def main(axe_file: str, html: str) -> int:
    """Audit every page; 1 when any has a violation."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    axe = Path(axe_file).read_text(encoding="utf-8")
    server, port = serve_docs(Path(html))
    found: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        for name in PAGES:
            found += violations(page, f"http://127.0.0.1:{port}/{name}", axe)
        for options in STUDIOS:
            found += audit_studio(page, options, axe)
        browser.close()
    server.shutdown()
    sys.stdout.write(
        "\n".join(found) + "\n"
        if found
        else f"no WCAG A/AA violation on {len(PAGES)} pages and {len(STUDIOS)} Studio pages\n"
    )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
