"""Modelly in the browser: static sites that run a model with Pyodide.

``modelly export-web model.py:Model --out site/`` (or ``export_web``) writes a page that
loads Pyodide from its CDN, installs Modelly from a wheel shipped in the site and runs the
model in a Web Worker, with a parameter panel, a plot and a space view. The parts:

- ``export``: ``WebExport`` and ``export_web``, the site writer;
- ``packages``: the Pyodide packages a model needs, found by running it;
- ``wheel``: the pure-Python Modelly wheel the site ships;
- ``runtime``: ``BrowserRun``, the Python the page's worker calls in Pyodide;
- ``snapshot``: the series and agent places the page draws.

The guide is ``docs/browser.md``.
"""

from modelly.web.export import PYODIDE_VERSION, WebExport, export_web
from modelly.web.runtime import BrowserRun

__all__ = ["PYODIDE_VERSION", "BrowserRun", "WebExport", "export_web"]
