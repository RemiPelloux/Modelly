"""The front-end files Solara's page needs, and filling their cache for offline use."""

import pytest

pytest.importorskip("solara")

from modelly.studio import assets

CSS = "@widgetti/app@1.0.0/dist/fonts.css"


def test_the_page_template_names_its_files():
    """RequireJS, Font Awesome and one Vuetify app with its minified script."""
    paths = assets.page_assets()
    assert any(p.startswith("requirejs@") for p in paths)
    assert any(p.startswith("font-awesome@") for p in paths)
    apps = {p.split("/")[1] for p in paths if p.startswith("@widgetti/")}
    assert len(apps) == 1
    scripts = [p for p in paths if p.endswith(".js") and "@widgetti" in p]
    assert scripts and all(p.endswith(".min.js") for p in scripts)
    assert all("{" not in p and not p.startswith("/") for p in paths)


def test_style_sheets_point_to_their_fonts():
    """Relative ``url()``s resolve next to the sheet; data and absolute URLs are skipped."""
    css = (
        "src: url(a.woff2?v=1) format('woff2'), url('../fonts/b.ttf#x');"
        "background: url(data:image/png;base64,AAAA); x: url(https://example.org/c.png)"
    )
    assert assets.style_references(CSS, css) == [
        "@widgetti/app@1.0.0/dist/a.woff2",
        "@widgetti/app@1.0.0/fonts/b.ttf",
    ]


def test_missing_and_fetch(tmp_path, monkeypatch):
    """An empty cache misses every page file; fetching fills it, sheets' fonts included."""
    page = assets.page_assets()
    assert assets.missing_assets(tmp_path) == page
    assert "front-end file(s)" in assets.warning(tmp_path)

    def fake_get_path(folder, path):
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        text = "src: url(extra.woff2);" if path.endswith(".css") else "x"
        target.write_text(text, encoding="utf-8")
        return target

    monkeypatch.setattr("solara.server.cdn_helper.get_path", fake_get_path)
    fetched = assets.fetch_assets(tmp_path)
    assert set(page) < set(fetched)
    assert any(p.endswith("/extra.woff2") for p in fetched)
    assert assets.missing_assets(tmp_path) == []
    assert assets.warning(tmp_path) is None


def test_the_command_reports_the_cache(tmp_path, monkeypatch, capsys):
    """Exit 1 and ``missing`` lines while files are missing."""
    monkeypatch.setattr(assets, "cache_folder", lambda: tmp_path)
    assert assets.main([]) == assets.EXIT_MISSING
    out = capsys.readouterr().out
    assert "missing  requirejs@" in out
    assert f"cache: {tmp_path}" in out
