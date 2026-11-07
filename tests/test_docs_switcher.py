"""scripts/docs_switcher.py: the version menu names each version by its full release."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from docs_switcher import main


def build(folder, release):
    """A built version folder whose theme options record ``release``."""
    static = folder / "_static"
    static.mkdir(parents=True)
    options = f"const DOCUMENTATION_OPTIONS = {{\n    VERSION: '{release}',\n}};\n"
    (static / "documentation_options.js").write_text(options, encoding="utf-8")


def test_entries_carry_the_full_release(tmp_path):
    """The stable entry reads the root's release; older ones read their own folder."""
    build(tmp_path, "1.5.1")
    (tmp_path / "1.5").mkdir()  # redirects only: no _static
    build(tmp_path / "1.4", "1.4.3")
    (tmp_path / "1.3").mkdir()  # nothing to read: falls back to X.Y
    build(tmp_path / "dev", "dev")
    assert main([str(tmp_path)]) == 0
    entries = json.loads((tmp_path / "switcher.json").read_text(encoding="utf-8"))
    names = [(e["name"], e["version"]) for e in entries]
    assert names == [
        ("1.5.1 (stable)", "1.5"),
        ("dev", "dev"),
        ("1.4.3", "1.4"),
        ("1.3", "1.3"),
    ]
