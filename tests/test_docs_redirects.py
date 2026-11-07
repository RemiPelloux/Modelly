"""scripts/docs_redirects.py: the newest version's folder becomes redirects to the root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from docs_redirects import MARKER, main, to_redirects


def site(tmp_path):
    """A version folder with pages, a nested page, assets and text copies."""
    folder = tmp_path / "1.5"
    for name in ("index.html", "apis/core.html", "_modules/modelly/agent.html"):
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("<html>full page</html>", encoding="utf-8")
    (folder / "_static").mkdir()
    (folder / "_static" / "theme.css").write_text("body {}", encoding="utf-8")
    (folder / "searchindex.js").write_text("index", encoding="utf-8")
    (folder / "index.md").write_text("# Modelly", encoding="utf-8")
    return folder


def test_pages_redirect_to_the_same_path_at_the_root(tmp_path):
    """Every page, nested ones too, sends the reader to the same path one level up."""
    folder = site(tmp_path)
    assert to_redirects(folder) == 3
    nested = (folder / "apis" / "core.html").read_text(encoding="utf-8")
    assert 'content="0; url=../../apis/core.html"' in nested
    assert "location.hash" in nested
    deep = (folder / "_modules" / "modelly" / "agent.html").read_text(encoding="utf-8")
    assert "url=../../../_modules/modelly/agent.html" in deep


def test_assets_go_and_text_copies_stay(tmp_path):
    """Theme files and the search index go; the Markdown copy and the marker stay."""
    folder = site(tmp_path)
    to_redirects(folder)
    assert not (folder / "_static").exists()
    assert not (folder / "searchindex.js").exists()
    assert (folder / "index.md").read_text(encoding="utf-8") == "# Modelly"
    assert (folder / MARKER).is_file()


def test_command_line_needs_an_existing_folder(tmp_path, capsys):
    """A missing folder or missing arguments is a usage error."""
    assert main([str(tmp_path), "9.9"]) == 2
    assert main([]) == 2
    site(tmp_path)
    assert main([str(tmp_path), "1.5"]) == 0
    assert "3 pages now redirect" in capsys.readouterr().out
