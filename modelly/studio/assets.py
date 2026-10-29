"""Solara's front-end files, cached once so Studio runs with no network.

Solara's page loads its JavaScript, CSS and fonts through a proxy of the jsDelivr CDN on the
Studio server (``/_solara/cdn/...``): the first request for a file downloads it into a cache
folder (``share/solara/cdn`` in the environment, or ``SOLARA_ASSETS_PROXY_CACHE_DIR``) and
later ones are served from there, so the browser itself never leaves localhost. A machine
without internet access needs the cache filled beforehand::

    python -m modelly.studio.assets            # list what is cached and what is missing
    python -m modelly.studio.assets --fetch    # download what is missing (once, online)

The files are those Solara's page template names (the Vuetify app, its fonts, RequireJS,
Font Awesome) and the files their style sheets point to (the icon and text fonts). The
``solara-assets`` package that used to ship them lags behind Solara's releases, so Studio
does not rely on it. Copying the cache folder to another machine with the same Solara works
too. Studio's own code (the map's WebGL renderer included) ships inside Modelly.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from pathlib import Path

PAGE_TEMPLATE = "solara.html.j2"
CDN_REFERENCE = re.compile(r"\{\{cdn\}\}(/?[^\"'\s<>]+)")
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
VUE2_APP, VUE3_APP = "solara-vuetify-app@", "solara-vuetify3-app@"
MINIFIED, SCRIPT, STYLE = ".min.js", ".js", ".css"
EXIT_OK, EXIT_MISSING = 0, 1


def cache_folder() -> Path:
    """The folder Solara's CDN proxy caches files in."""
    from solara.server import settings  # noqa: PLC0415 (the viz extra)

    return Path(settings.assets.proxy_cache_dir)


def _substitutions() -> dict[str, str]:
    """The template variables that appear inside its CDN paths, with their values."""
    import ipywidgets  # noqa: PLC0415 (the viz extra)
    from solara.server import settings  # noqa: PLC0415

    major = ipywidgets.__version__.split(".")[0]
    return {
        "{{ipywidget_major_version}}": major,
        "{{assets.fontawesome_path}}": settings.assets.fontawesome_path,
    }


def _wanted(path: str, vue3: bool, paths: set[str]) -> bool:
    """Whether the page loads ``path``: its Vue version's app, minified scripts only."""
    if (VUE2_APP in path and vue3) or (VUE3_APP in path and not vue3):
        return False
    unminified = path.endswith(SCRIPT) and not path.endswith(MINIFIED)
    return not (unminified and path[: -len(SCRIPT)] + MINIFIED in paths)


def page_assets() -> list[str]:
    """The CDN paths Solara's page template loads, for this Solara and ipywidgets."""
    import ipyvue  # noqa: PLC0415 (the viz extra)
    import solara.server.server as server  # noqa: PLC0415

    template = Path(server.__file__).parent / "templates" / PAGE_TEMPLATE
    text = template.read_text(encoding="utf-8")
    for name, value in _substitutions().items():
        text = text.replace(name, value)
    paths = {match.lstrip("/") for match in CDN_REFERENCE.findall(text)}
    vue3 = ipyvue.__version__.startswith("3")
    return sorted(p for p in paths if "{" not in p and _wanted(p, vue3, paths))


def style_references(path: str, css: str) -> list[str]:
    """The files the style sheet at CDN ``path`` points to, as CDN paths."""
    found = set()
    for reference in CSS_URL.findall(css):
        if reference.startswith(("data:", "http:", "https:", "//")):
            continue
        clean = reference.split("?")[0].split("#")[0]
        found.add(posixpath.normpath(posixpath.join(posixpath.dirname(path), clean)))
    return sorted(found)


def required_assets(folder: Path | None = None) -> list[str]:
    """The page's files, and the files the cached style sheets among them point to."""
    folder = folder or cache_folder()
    paths = page_assets()
    for path in [p for p in paths if p.endswith(STYLE)]:
        cached = folder / path
        if cached.is_file():
            paths += style_references(path, cached.read_text(encoding="utf-8"))
    return sorted(set(paths))


def missing_assets(folder: Path | None = None) -> list[str]:
    """The files Studio's page needs that are not in the cache yet."""
    folder = folder or cache_folder()
    return [p for p in required_assets(folder) if not (folder / p).is_file()]


def fetch_assets(folder: Path | None = None) -> list[str]:
    """Download every missing file into the cache (style sheets first); those fetched."""
    from solara.server.cdn_helper import get_path  # noqa: PLC0415 (the viz extra)

    folder = folder or cache_folder()
    fetched = []
    for _ in range(2):  # the second pass fetches what the new style sheets point to
        for path in missing_assets(folder):
            get_path(folder, path)
            fetched.append(path)
    return fetched


def warning(folder: Path | None = None) -> str | None:
    """The line ``modelly studio`` prints when files are missing, else None."""
    missing = missing_assets(folder)
    if not missing:
        return None
    return (
        f"modelly studio: {len(missing)} front-end file(s) are not cached yet; the "
        "server downloads them from cdn.jsdelivr.net when the page first asks. To run "
        "offline, run `python -m modelly.studio.assets --fetch` once while online.\n"
    )


def main(argv: list[str] | None = None) -> int:
    """List the cached and missing files; with ``--fetch``, download the missing ones."""
    parser = argparse.ArgumentParser(
        prog="python -m modelly.studio.assets", description=__doc__.splitlines()[0]
    )
    parser.add_argument("--fetch", action="store_true", help="download missing files")
    args = parser.parse_args(argv)
    folder = cache_folder()
    if args.fetch:
        for path in fetch_assets(folder):
            sys.stdout.write(f"fetched  {path}\n")
    missing = set(missing_assets(folder))
    for path in required_assets(folder):
        sys.stdout.write(f"{'missing' if path in missing else 'cached '}  {path}\n")
    sys.stdout.write(f"cache: {folder}\n")
    return EXIT_MISSING if missing else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
