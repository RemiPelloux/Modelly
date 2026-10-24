"""Version switcher settings for the published docs.

The site holds one build per minor release (``/1.1/``, ``/1.0/``), the main branch
(``/dev/``) and a copy of the newest minor at the root. The switcher menu reads
``switcher.json`` from the site root; ``scripts/docs_switcher.py`` writes it when the
site is assembled, after the build, so Sphinx does not check it.

``MODELLY_DOCS_VERSION`` names the build: ``dev`` or ``X.Y``; without it the build is
the installed package's ``X.Y``. ``MODELLY_DOCS_RELEASE`` overrides the full release,
for a tag built against another installed version.
"""

import os

SITE_URL = "https://remipelloux.github.io/Modelly/"
SWITCHER_URL = f"{SITE_URL}switcher.json"
VERSION_ENV = "MODELLY_DOCS_VERSION"
RELEASE_ENV = "MODELLY_DOCS_RELEASE"
DEV_VERSION = "dev"
MINOR_PARTS = 2  # X.Y of X.Y.Z


def docs_version(release: str) -> str:
    """Return the switcher version of this build: the env var, else the release's X.Y."""
    return os.environ.get(VERSION_ENV) or ".".join(release.split(".")[:MINOR_PARTS])


def apply_versioning(conf: dict) -> None:
    """Set the version, the switcher and the old-version banner in a conf.py namespace."""
    release = os.environ.get(RELEASE_ENV) or conf["release"]
    version = docs_version(release)
    if version == DEV_VERSION:  # the theme's banner calls a "dev" release unstable
        release = DEV_VERSION
    options = conf["html_theme_options"]
    options["navbar_start"] = ["navbar-logo", "version-switcher"]
    options["switcher"] = {"json_url": SWITCHER_URL, "version_match": version}
    options["check_switcher"] = False
    options["show_version_warning_banner"] = True
    conf["version"] = version
    conf["release"] = release
