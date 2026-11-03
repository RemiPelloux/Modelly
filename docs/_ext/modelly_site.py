"""What the docs site gives search engines and language models, beyond its HTML pages.

At page writing, each page gets a meta description (its own, or its first paragraph), Open
Graph and Twitter tags, a ``text/markdown`` alternate link and JSON-LD structured data. When
the build finishes, every page also gets a Markdown copy next to its HTML (``decide.html``
and ``decide.md``), and the site gets ``llms.txt`` (the pages, in reading order, with their
descriptions; see llmstxt.org), ``llms-full.txt`` (every page's Markdown, concatenated),
``sitemap.xml`` and ``robots.txt``. The dev build's URLs live under ``dev/``.
"""

from __future__ import annotations

import json
import re
from html import escape, unescape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from html_markdown import article_markdown

DESCRIPTION_LENGTH = 160
SKIPPED_DOCS = {"genindex", "search", "py-modindex"}
SUMMARY = (
    "Modelly is an open-source Python framework for agent-based modeling: agents with a "
    "step(), state in numpy columns, grids, networks, continuous and geographic space, "
    "seeded reproducible runs, experiments, calibration, sensitivity analysis, decisions, "
    "a model hub and a browser Studio."
)
REPOSITORY = "https://github.com/RemiPelloux/Modelly"
SOCIAL_CARD = "_static/social-card.png"  # 1200 x 630, docs/_static
SOCIAL_CARD_ALT = (
    "Modelly: agent-based models in Python. An epidemic spreading on a grid."
)
TAG = re.compile(r"<[^>]+>")
PARAGRAPH = re.compile(r"<p>(.*?)</p>", re.S)
META_DESCRIPTION = re.compile(r'<meta content="([^"]*)" name="description"')  # MyST's
WRITTEN_DESCRIPTION = re.compile(r'<meta name="description" content="([^"]*)"')  # ours


def site_base(app) -> str:
    """The URL the build is served from: the site root, or ``dev/`` for the dev build."""
    base = app.config.html_baseurl
    return base + "dev/" if app.config.version == "dev" else base


def plain(html: str) -> str:
    """The text of an HTML fragment, on one line."""
    return re.sub(r"\s+", " ", unescape(TAG.sub("", html))).strip()


def shorten(text: str, length: int = DESCRIPTION_LENGTH) -> str:
    """``text`` cut at a word before ``length`` characters, with an ellipsis when cut."""
    if len(text) <= length:
        return text
    return text[: length - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def page_description(body: str, metatags: str) -> tuple[str, bool]:
    """The page's description and whether it is new: the written one, else its first paragraph."""
    written = META_DESCRIPTION.search(metatags)
    if written:
        return unescape(written.group(1)), False
    for paragraph in PARAGRAPH.findall(body):
        text = plain(paragraph)
        if len(text) > 60:
            return shorten(text), True
    return SUMMARY, True


def structured_data(app, pagename: str, title: str, description: str, url: str) -> dict:
    """JSON-LD: the software on the home page, a technical article on every other page."""
    page = {"@context": "https://schema.org", "description": description, "url": url}
    if pagename == app.config.root_doc:
        return page | {
            "@type": "SoftwareSourceCode",
            "name": "Modelly",
            "codeRepository": REPOSITORY,
            "programmingLanguage": "Python",
            "license": "https://www.apache.org/licenses/LICENSE-2.0",
            "version": app.config.release,
        }
    site = {"@type": "WebSite", "name": "Modelly documentation", "url": site_base(app)}
    return page | {"@type": "TechArticle", "headline": title, "isPartOf": site}


def social_tags(title: str, description: str, url: str, base: str) -> list[str]:
    """Open Graph and Twitter tags: the page's title, description and address, the card."""
    pairs = (("og:title", title), ("og:description", description), ("og:url", url),
             ("og:type", "website"), ("og:site_name", "Modelly"),
             ("og:image", base + SOCIAL_CARD), ("og:image:width", "1200"),
             ("og:image:height", "630"), ("og:image:alt", SOCIAL_CARD_ALT))  # fmt: skip
    tags = [f'<meta property="{k}" content="{escape(v)}" />' for k, v in pairs]
    return [*tags, '<meta name="twitter:card" content="summary_large_image" />']


def add_page_tags(
    app, pagename: str, templatename: str, context: dict, doctree
) -> None:
    """Description, social tags, the Markdown alternate and JSON-LD of one page."""
    if doctree is None or pagename in SKIPPED_DOCS:
        return
    title = plain(context.get("title", "")) or "Modelly"
    metatags = context.get("metatags", "")
    description, new = page_description(context.get("body", ""), metatags)
    uri = app.builder.get_target_uri(pagename)
    url = site_base(app) + uri
    tags = (
        [f'<meta name="description" content="{escape(description)}" />'] if new else []
    )
    tags += social_tags(title, description, url, site_base(app))
    markdown = Path(uri).with_suffix(".md").name
    tags.append(f'<link rel="alternate" type="text/markdown" href="{markdown}" />')
    data = structured_data(app, pagename, title, description, url)
    # A "</" inside a string must not close the script element.
    data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    tags.append(f'<script type="application/ld+json">{data}</script>')
    context["metatags"] = metatags + "\n" + "\n".join(tags)


def reading_order(env) -> list[str]:
    """Every document, in the order the toctrees list them, the rest after."""
    seen: list[str] = []
    stack = [env.config.root_doc]
    while stack:
        doc = stack.pop()
        if doc in seen or doc not in env.found_docs:
            continue
        seen.append(doc)
        stack.extend(reversed(env.toctree_includes.get(doc, [])))
    return seen + sorted(set(env.found_docs) - set(seen))


Page = tuple[str, str, str, str]  # the URL of its .md, title, description, Markdown


def page_markdown(app, doc: str) -> Page | None:
    """Write one page's Markdown copy next to its HTML; None for a page without content."""
    out, base = Path(app.outdir), site_base(app)
    uri = app.builder.get_target_uri(doc)
    html_path = out / uri
    if doc in SKIPPED_DOCS or not html_path.is_file():
        return None
    html = html_path.read_text(encoding="utf-8")
    text = article_markdown(html, base + uri)
    if not text.strip():
        return None
    md_path = html_path.with_suffix(".md")
    md_path.write_text(text, encoding="utf-8")
    found = META_DESCRIPTION.search(html) or WRITTEN_DESCRIPTION.search(html)
    description = unescape(found.group(1)) if found else ""
    title = plain(app.env.titles[doc].astext()) if doc in app.env.titles else doc
    return base + md_path.relative_to(out).as_posix(), title, description, text


def write_markdown(app, docs: list[str]) -> list[Page]:
    """Write every page's Markdown copy; return the pages that have one."""
    return [page for doc in docs if (page := page_markdown(app, doc)) is not None]


SECTIONS = (
    ("tutorials/", "Tutorials"),
    ("zoo/", "Model zoo"),
    ("examples/", "Examples"),
    ("course/", "Course"),
    ("apis/", "API reference"),
    ("roadmap/", "Roadmap"),
    ("design/", "Design notes"),
    ("translations/", "Translations"),
)


def section_of(url: str, base: str) -> str:
    """The llms.txt section of a page, from the folder it sits in."""
    path = url[len(base) :]
    return next(
        (name for prefix, name in SECTIONS if path.startswith(prefix)), "Guides"
    )


def llms_index(pages: list[Page], base: str) -> str:
    """``llms.txt``: a title, the summary, then one link list per section."""
    lines = [
        "# Modelly",
        "",
        f"> {SUMMARY}",
        "",
        (
            "Install with `pip install modelly-abm`. Every page below is also served as "
            f"Markdown; all of them in one file: {base}llms-full.txt"
        ),
        "",
    ]
    groups: dict[str, list[str]] = {}
    for url, title, description, _ in pages:
        entry = f"- [{title}]({url})" + (f": {description}" if description else "")
        groups.setdefault(section_of(url, base), []).append(entry)
    for name in ["Guides", *(n for _, n in SECTIONS)]:
        if name in groups:
            lines += [f"## {name}", "", *groups[name], ""]
    return "\n".join(lines)


def sitemap(app, docs: list[str]) -> str:
    """``sitemap.xml`` of every HTML page."""
    base = site_base(app)
    root = app.config.root_doc
    urls = [
        f"  <url><loc>{xml_escape(base + ('' if d == root else app.builder.get_target_uri(d)))}</loc></url>"
        for d in docs
        if d not in SKIPPED_DOCS
    ]
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    return (
        head
        + '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def write_site_files(app, exception) -> None:
    """The Markdown copies, llms.txt, llms-full.txt, sitemap.xml and robots.txt."""
    if exception is not None or app.builder.format != "html":
        return
    out, base = Path(app.outdir), site_base(app)
    docs = reading_order(app.env)
    pages = write_markdown(app, docs)
    (out / "llms.txt").write_text(llms_index(pages, base), encoding="utf-8")
    full = "\n\n".join(f"<!-- {url} -->\n\n{text}" for url, _, _, text in pages)
    (out / "llms-full.txt").write_text(full, encoding="utf-8")
    (out / "sitemap.xml").write_text(sitemap(app, docs), encoding="utf-8")
    robots = (
        f"User-agent: *\nAllow: /\n\nSitemap: {app.config.html_baseurl}sitemap.xml\n"
    )
    (out / "robots.txt").write_text(robots, encoding="utf-8")


def setup(app) -> dict:
    """Register the page tags and the site files."""
    app.connect("html-page-context", add_page_tags)
    app.connect("build-finished", write_site_files)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
