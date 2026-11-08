"""Take the Studio screenshots in docs/studio.md, as PNG files in docs/images/studio.

Starts ``modelly studio`` on the models each picture shows, drives it in headless Chromium
and saves ``model.png`` (Wolf-Sheep after 40 steps), ``profiler.png`` (the same run's
profile), ``timeline.png`` (a Boltzmann run scrubbed back to step 7) and ``lint.png`` (the
lint panel explaining MDL001 for a model that draws from the global ``random``). Run from
the repository root, on any OS, after changing Studio's layout:

    python tools/studio/screenshots.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import sync_playwright
from record_tour import START_TIMEOUT_S, WAIT_MS, free_port, wait_until_up

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "images" / "studio"
SIZE = {"width": 1280, "height": 800}
SETTLE_MS = 1500
WOLF_SHEEP = [
    "modelly.examples.advanced.wolf_sheep.model:WolfSheep",
    "--portrayal",
    "modelly/examples/advanced/wolf_sheep/app.py:wolf_sheep_portrayal",
]
BOLTZMANN = ["modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"]
RANDOM_WALK = """import random

from modelly import Agent, Model


class Walker(Agent):
    def step(self):
        if random.random() < 0.5:
            self.wealth = 1


class RandomWalk(Model):
    def __init__(self, n=10, rng=None):
        super().__init__(rng=rng)
        Walker.create_agents(self, n)

    def step(self):
        self.agents.shuffle_do("step")
"""


def settle(page) -> None:
    """No focus ring, hover or ripple left from driving the page, then a pause."""
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.mouse.move(SIZE["width"] - 2, SIZE["height"] // 2)
    page.wait_for_timeout(SETTLE_MS)


def run(page, steps: int) -> None:
    """Run ``steps`` steps with the toolbar's Run button."""
    page.get_by_text("Timeline").first.wait_for(timeout=WAIT_MS)
    field = page.get_by_role("textbox", name="steps")
    field.fill(str(steps))
    field.press("Enter")
    page.get_by_role("button", name=f"Run {steps}").click()
    page.get_by_text(f"step {steps}", exact=True).wait_for(timeout=WAIT_MS)
    settle(page)


def wolf_sheep(page) -> None:
    """The Model tab after 40 steps, then the Profiler tab."""
    run(page, 40)
    page.screenshot(path=OUT / "model.png")
    page.get_by_role("tab", name="Profiler").click()
    page.get_by_text("step(s) profiled").wait_for(timeout=WAIT_MS)
    settle(page)
    page.screenshot(path=OUT / "profiler.png")


def boltzmann(page) -> None:
    """Twenty steps, scrubbed back to step 7."""
    run(page, 20)
    slider = page.locator(".mx-timeline").get_by_role("slider").first
    slider.focus()
    for _ in range(13):
        slider.press("ArrowLeft")
        page.wait_for_timeout(150)
    page.get_by_text("showing step 7 of 20").wait_for(timeout=WAIT_MS)
    settle(page)
    page.screenshot(path=OUT / "timeline.png")


def random_walk(page) -> None:
    """The Lint tab with the MDL001 finding opened."""
    page.get_by_text("Timeline").first.wait_for(timeout=WAIT_MS)
    page.get_by_role("tab", name="Lint").click()
    page.get_by_role("button", name="MDL001").click()
    page.get_by_text("Instead:").first.wait_for(timeout=WAIT_MS)
    settle(page)
    page.screenshot(path=OUT / "lint.png")


def shoot(target: list[str], take: Callable) -> None:
    """Serve Studio on ``target`` and run ``take`` on its page."""
    port = free_port()
    command = [sys.executable, "-m", "modelly", "studio", *target]
    server = subprocess.Popen([*command, "--port", str(port), "--no-browser"], cwd=ROOT)
    url = f"http://127.0.0.1:{port}"
    try:
        wait_until_up(url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport=SIZE)
            page.goto(url)
            take(page)
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=START_TIMEOUT_S)


def main() -> int:
    """Take every screenshot; the exit status."""
    shoot(WOLF_SHEEP, wolf_sheep)
    shoot(BOLTZMANN, boltzmann)
    with tempfile.TemporaryDirectory() as folder:
        model = Path(folder) / "random_walk.py"
        model.write_text(RANDOM_WALK, encoding="utf-8")
        shoot([f"{model}:RandomWalk"], random_walk)
    for name in ("model", "profiler", "timeline", "lint"):
        sys.stdout.write(f"{(OUT / name).with_suffix('.png').relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
