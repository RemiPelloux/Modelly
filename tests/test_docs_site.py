"""The docs build's Markdown copies and llms.txt (docs/_ext)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "docs" / "_ext"))

from html_markdown import article_markdown
from modelly_site import llms_index, page_description, shorten

BASE = "https://example.org/docs/"
PAGE = """<html><body><nav>menu</nav><article class="bd-article" role="main">
<h1>Decisions<a class="headerlink" href="#d">#</a></h1>
<p><code>modelly.decide</code> compares <strong>strategies</strong>, see
<a href="experiments.html">experiments</a>.</p>
<ul><li><p>one</p></li><li><p>two</p></li></ul>
<div class="highlight-python notranslate"><div class="highlight"><pre>x = 1
</pre><button class="copybtn">copy</button></div></div>
<div aria-hidden="true">a chart</div>
<table><thead><tr><th>Model</th><th>Speed</th></tr></thead>
<tbody><tr><td>SIR</td><td>26x</td></tr></tbody></table>
<dl class="py class"><dt class="sig sig-object py"><span>class </span><span>Strategy</span>
<span>(name: str)</span><a class="headerlink" href="#s">#</a></dt>
<dd><p>A named intervention.</p></dd></dl>
</article></body></html>"""


def test_article_markdown_keeps_the_content_and_drops_the_chrome():
    """Headings, inline marks, links, lists, code, tables and signatures survive; chrome does not."""
    md = article_markdown(PAGE, BASE + "decide.html")
    assert md.startswith("# Decisions\n")
    assert "`modelly.decide` compares **strategies**" in md
    assert f"[experiments]({BASE}experiments.html)" in md
    assert "- one\n- two" in md
    assert "```python\nx = 1\n```" in md
    assert "| Model | Speed |\n|---|---|\n| SIR | 26x |" in md
    assert "#### `class Strategy (name: str)`" in md
    for chrome in ("menu", "copy", "a chart", "#"):
        assert chrome not in md.replace("# Decisions", "").replace("####", "")


def test_a_page_without_an_article_has_no_markdown():
    """Pages without an article (redirects, search) get no copy."""
    assert article_markdown("<html><body><p>x</p></body></html>") == ""


def test_the_description_is_the_written_one_else_the_first_long_paragraph():
    """A written description wins; otherwise the first long paragraph, shortened."""
    written = '<meta content="Written." name="description" />'
    assert page_description("<p>" + "a " * 50 + "</p>", written) == ("Written.", False)
    text, new = page_description("<p>Short.</p><p>" + "word " * 60 + "</p>", "")
    assert new and text.endswith("…") and len(text) <= 160


def test_shorten_cuts_at_a_word():
    """Shortening stops at a word and marks the cut."""
    assert shorten("one two three", 9) == "one two…"
    assert shorten("short", 9) == "short"


def test_llms_index_groups_pages_by_folder():
    """llms.txt lists guides first and API pages under their own heading."""
    pages = [(BASE + "decide.md", "Decisions", "Compare strategies.", ""),
             (BASE + "apis/decide.md", "decide", "", "")]  # fmt: skip
    index = llms_index(pages, BASE)
    assert index.startswith("# Modelly\n\n> ")
    guides, api = index.index("## Guides"), index.index("## API reference")
    assert (
        guides
        < index.index("- [Decisions](https://example.org/docs/decide.md): Compare")
        < api
    )
    assert "- [decide](https://example.org/docs/apis/decide.md)\n" in index
