"""The main content of a built Sphinx page, as plain Markdown an LLM or a person can paste.

``article_markdown(html)`` takes the ``<article class="bd-article">`` of a pydata-sphinx-theme
page and writes headings, paragraphs, lists, tables, code blocks (with their language),
links and inline code as Markdown, dropping what only the browser needs: header anchors,
copy buttons, scripts, styles and anything ``aria-hidden`` or marked ``data-md="skip"``.
API pages come out as their signatures and docstrings. It uses the standard library only,
so the docs build needs nothing more.
"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

SKIP = {"script", "style", "button", "nav", "form", "svg", "canvas", "template"}
SKIP_CLASSES = ("headerlink", "copybtn", "viewcode-link")
BLOCKS = {"p", "caption", "div", "section", "li", "dd", "dt", "tr", "table", "blockquote",
          "figure", "dl"}  # fmt: skip
HEADINGS = {f"h{i}": i for i in range(1, 7)}
EMPHASIS = {"strong": "**", "b": "**", "em": "*", "i": "*"}
LANGUAGE = re.compile(r"highlight-([a-z0-9_+-]+)")
ARTICLE = re.compile(r'<article class="bd-article"[^>]*>(.*?)</article>', re.S)


def _one_line(parts: list[str]) -> str:
    """The text of ``parts`` with its runs of whitespace made single spaces."""
    return re.sub(r"\s+", " ", "".join(parts)).strip()


class _Converter(HTMLParser):
    """Walks the article's HTML and builds Markdown lines."""

    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base, self.out, self.line = base, [], []
        self.skip, self.skip_tag, self.pre, self.lists, self.link = (
            0,
            "",
            None,
            [],
            None,
        )
        self.language = ""  # of the code block about to open
        self.row, self.table, self.heading = None, None, None
        self.signature = (
            None  # the text of an API signature (<dt class="sig">) being read
        )

    # --- output helpers -------------------------------------------------------------------
    def flush(self) -> None:
        text = re.sub(r"[ \t]+", " ", "".join(self.line)).strip()
        if text:
            self.out.append(text)
        self.line = []

    def blank(self) -> None:
        self.flush()
        if self.out and self.out[-1] != "":
            self.out.append("")

    def block_break(self, tag: str) -> None:
        """The break a block element makes: a new line inside a list item, else a blank line."""
        if tag not in BLOCKS or self.at_bullet():
            return
        if self.lists and tag in ("p", "li"):
            self.flush()
        else:
            self.blank()

    def at_bullet(self) -> bool:
        """Whether the line holds only a list marker, which a paragraph inside must keep."""
        return "".join(self.line).strip() in ("-", "1.")

    # --- opening tags ---------------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        classes = a.get("class") or ""
        if (
            self.skipping(tag, a, classes)
            or self.pre is not None
            or self.signature is not None
        ):
            return
        opened = self.open_block(tag, classes) or self.open_inline(tag, a)
        if not opened:
            self.block_break(tag)

    def skipping(self, tag: str, a: dict, classes: str) -> bool:
        """Count nested tags inside a skipped element; start skipping one that is dropped."""
        if self.skip:
            self.skip += tag == self.skip_tag
            return True
        hidden = a.get("aria-hidden") == "true" or a.get("data-md") == "skip"
        if hidden or tag in SKIP or any(c in classes for c in SKIP_CLASSES):
            self.skip, self.skip_tag = 1, tag
            return True
        return False

    def open_block(self, tag: str, classes: str) -> bool:
        """Signatures, code, headings, lists and tables; whether ``tag`` was one."""
        if tag == "dt" and "sig" in classes.split():
            self.blank()
            self.signature = []
        elif tag == "div" and "highlight-" in classes:
            match = LANGUAGE.search(classes)
            self.language = match.group(1) if match else ""
            return False  # still a block: the blank line before the code
        elif tag == "pre":
            self.blank()
            self.pre = []
        elif tag in HEADINGS:
            self.blank()
            self.heading = HEADINGS[tag]
        elif tag in ("ul", "ol"):
            self.flush()
            self.lists.append([tag, 0])
        elif tag == "li":
            self.open_item()
        else:
            return self.open_table(tag)
        return True

    def open_item(self) -> None:
        """A list item: its marker, indented by the depth of the list."""
        self.flush()
        kind = self.lists[-1] if self.lists else ["ul", 0]
        kind[1] += 1
        indent = "  " * (len(self.lists) - 1)
        self.line.append(f"{indent}{'1.' if kind[0] == 'ol' else '-'} ")

    def open_table(self, tag: str) -> bool:
        """A table, a row or a cell; whether ``tag`` was one."""
        if tag == "table":
            self.blank()
            self.table = []
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.flush()
            self.row.append("")
        else:
            return False
        return True

    def open_inline(self, tag: str, a: dict) -> bool:
        """Links, code, emphasis, images, line breaks and terms; whether ``tag`` was one."""
        if tag == "a" and a.get("href"):
            self.link = (urljoin(self.base, a["href"]), len(self.line))
        elif tag == "code" and self.row is None:
            self.line.append("`")
        elif tag in EMPHASIS:
            self.line.append(EMPHASIS[tag])
        elif tag == "img" and a.get("alt"):
            self.line.append(f"![{a['alt']}]({urljoin(self.base, a.get('src', ''))})")
        elif tag == "br":
            self.line.append("  \n")
        elif tag == "dt":
            self.blank()
            self.line.append("**")
        else:
            return False
        return True

    # --- closing tags ---------------------------------------------------------------------
    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            self.skip -= tag == self.skip_tag
        elif self.pre is not None:
            if tag == "pre":
                self.close_code()
        elif self.signature is not None:
            if tag == "dt":
                self.out += [f"#### `{_one_line(self.signature)}`", ""]
                self.signature = None
        elif not (self.close_block(tag) or self.close_inline(tag)):
            self.block_break(tag)

    def close_code(self) -> None:
        """A fenced code block with the language of its highlight."""
        code = "".join(self.pre).rstrip("\n")
        self.out += [f"```{self.language}", code, "```", ""]
        self.pre, self.language = None, ""

    def close_block(self, tag: str) -> bool:
        """Headings, lists and tables; whether ``tag`` was one."""
        if tag in HEADINGS and self.heading:
            text = "".join(self.line).strip()
            self.line = []
            if text:
                self.out += ["#" * self.heading + " " + text, ""]
            self.heading = None
        elif tag in ("ul", "ol"):
            self.flush()
            if self.lists:
                self.lists.pop()
            if not self.lists:
                self.blank()
        elif tag in ("td", "th") and self.row is not None:
            self.row[-1] = _one_line(self.line).replace("|", "\\|")
            self.line = []
        elif tag == "tr" and self.row is not None and self.table is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.write_table()
        else:
            return False
        return True

    def close_inline(self, tag: str) -> bool:
        """Links, code, emphasis and terms; whether ``tag`` was one."""
        if tag == "a" and self.link is not None:
            href, start = self.link
            text = "".join(self.line[start:]).strip()
            self.line = self.line[:start] + ([f"[{text}]({href})"] if text else [])
            self.link = None
        elif tag == "code" and self.row is None:
            self.line.append("`")
        elif tag in EMPHASIS:
            self.line.append(EMPHASIS[tag])
        elif tag == "dt":
            self.line.append("**")
            self.blank()
        else:
            return False
        return True

    # --- text -----------------------------------------------------------------------------
    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.pre is not None:
            self.pre.append(data)
        elif self.signature is not None:
            self.signature.append(data)
        else:
            self.line.append(data.replace("\n", " "))

    def write_table(self) -> None:
        """The rows read so far as a Markdown table, the first one as its header."""
        rows = [r for r in self.table if any(c for c in r)]
        self.table = None
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        self.out += ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
        self.out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        self.out.append("")


def article_markdown(html: str, base: str = "") -> str:
    """The Markdown of a built page's article; empty when the page has none."""
    match = ARTICLE.search(html)
    if not match:
        return ""
    converter = _Converter(base)
    converter.feed(match.group(1))
    converter.flush()
    text = "\n".join(converter.out)
    text = re.sub(r"\n{3,}", "\n\n", unescape(text))
    return text.strip() + "\n"


__all__ = ["article_markdown"]
