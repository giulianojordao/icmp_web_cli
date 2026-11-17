"""Render a small, safe subset of HTML as readable terminal text (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
import shutil
import sys
import textwrap
from urllib.parse import urlsplit

# Some tags contain non-display content. Never interpret JavaScript or CSS.
SKIP = {"head", "script", "style", "noscript", "svg", "iframe", "object", "template"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BLOCK = {"html", "body", "main", "section", "article", "header", "footer", "nav",
         "div", "p", "blockquote", "pre", "ul", "ol", "li", "table", "tr",
         "h1", "h2", "h3", "h4", "h5", "h6", "hr"}
ANSI = {"reset": "\033[0m", "bold": "\033[1m", "cyan": "\033[36m", "green": "\033[32m", "dim": "\033[2m", "yellow": "\033[33m"}


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)


class HTMLTree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs):
        self.stack[-1].children.append(Node(tag, {k: (v or "") for k, v in attrs}))

    def handle_endtag(self, tag: str):
        # Tolerate simple malformed HTML; never climb past root.
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str):
        self.stack[-1].children.append(data)


def _clean(value: str) -> str:
    """Drop terminal control sequences so remote page text can't execute them."""
    return "".join(ch for ch in value if ch in "\n\t" or (ch.isprintable() and ch != "\x1b"))


def _inline(node: Node | str) -> str:
    if isinstance(node, str):
        return _clean(node)
    if node.tag in SKIP:
        return ""
    if node.tag == "br":
        return "\n"
    if node.tag == "img":
        return f"[imagem: {_clean(node.attrs.get('alt', 'sem descrição'))}]"
    rendered = "".join(_inline(child) for child in node.children)
    if node.tag == "a":
        href = _clean(node.attrs.get("href", "")).strip()
        # Do not make script/data link schemes actionable.
        if urlsplit(href).scheme in ("http", "https", "mailto") or href.startswith(("/", "#")):
            return f"{rendered.strip()} ({href})" if href and href != rendered.strip() else rendered
    return rendered


class TerminalRenderer:
    def __init__(self, width: int | None = None, color: bool | None = None):
        self.width = max(40, width or min(shutil.get_terminal_size((88, 24)).columns - 2, 120))
        self.color = sys.stdout.isatty() if color is None else color
        self.lines: list[str] = []

    def style(self, text: str, *styles: str) -> str:
        if not self.color or not text:
            return text
        return "".join(ANSI[s] for s in styles) + text + ANSI["reset"]

    def blank(self):
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def line(self, text: str = "", *, color: str | None = None):
        self.lines.append(self.style(text, color) if color else text)

    def paragraph(self, text: str, indent: str = "", style: str | None = None):
        text = _clean(text)
        for part in text.split("\n"):
            part = re.sub(r"[ \t]+", " ", part).strip()
            if not part:
                continue
            wrapped = textwrap.wrap(part, width=max(20, self.width - len(indent)),
                                    break_long_words=False, break_on_hyphens=False)
            for segment in wrapped or [""]:
                self.line(indent + segment, color=style)

    def render(self, document: str) -> str:
        parser = HTMLTree()
        parser.feed(document)
        self.lines = []
        self.line(self.style("═" * min(self.width, 82), "cyan"))
        self._children(parser.root)
        while self.lines and not self.lines[-1]:
            self.lines.pop()
        self.line(self.style("═" * min(self.width, 82), "cyan"))
        return "\n".join(self.lines) + "\n"

    def _children(self, node: Node):
        inline_parts: list[str] = []

        def flush():
            if inline_parts:
                value = "".join(inline_parts).strip()
                if value:
                    self.paragraph(value)
                inline_parts.clear()

        for child in node.children:
            if isinstance(child, str):
                inline_parts.append(child)
            elif child.tag in SKIP:
                continue
            elif child.tag in BLOCK:
                flush()
                self._element(child)
            else:
                inline_parts.append(_inline(child))
        flush()

    def _element(self, node: Node):
        tag = node.tag
        classes = set(node.attrs.get("class", "").split())
        if tag in {"html", "body", "main", "section", "article", "header", "nav"}:
            self._children(node)
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.blank()
            prefix = "#" * (int(tag[1]) if int(tag[1]) < 4 else 3) + " "
            self.paragraph(_inline(node), prefix, "cyan" if tag == "h1" else "bold")
            self.blank()
        elif tag == "p":
            self.blank()
            self.paragraph(_inline(node))
            self.blank()
        elif tag == "div" and "eyebrow" in classes:
            self.blank()
            self.paragraph(_inline(node).strip(), style="green")
        elif tag == "div" and "metric" in classes:
            primary = next((_inline(c).strip() for c in node.children if isinstance(c, Node) and c.tag == "b"), "")
            sub = next((_inline(c).strip() for c in node.children if isinstance(c, Node) and c.tag == "small"), "")
            self.line(f"  • {primary:<19} {sub}")
        elif tag == "div" and "console" in classes:
            self.blank()
            self.line(self.style(" TERMINAL ", "green"))
            for child in node.children:
                if isinstance(child, Node) and child.tag == "div":
                    self.paragraph(_inline(child), indent="  ", style="dim")
            self.blank()
        elif tag == "div":
            self._children(node)
        elif tag in {"ul", "ol"}:
            self.blank()
            index = 0
            for child in node.children:
                if isinstance(child, Node) and child.tag == "li":
                    index += 1
                    marker = "• " if tag == "ul" else f"{index}. "
                    self.paragraph(_inline(child), indent="  " + marker)
            self.blank()
        elif tag == "blockquote":
            self.blank()
            self.paragraph(_inline(node), indent="│ ")
            self.blank()
        elif tag == "pre":
            self.blank()
            for line in _clean(_inline(node)).strip("\n").split("\n"):
                self.line("  " + line[:self.width - 2], color="green")
            self.blank()
        elif tag == "footer":
            self.blank()
            self.paragraph(_inline(node), style="dim")
        elif tag == "hr":
            self.line("─" * min(self.width, 82), color="dim")
        elif tag == "table":
            self.blank()
            for tr in self._descendant_rows(node):
                cells = [_inline(td).strip() for td in tr.children
                         if isinstance(td, Node) and td.tag in {"th", "td"}]
                if cells:
                    self.paragraph("  |  ".join(cells))
            self.blank()
        else:
            self._children(node)

    @staticmethod
    def _descendant_rows(node: Node):
        for child in node.children:
            if isinstance(child, Node):
                if child.tag == "tr":
                    yield child
                else:
                    yield from TerminalRenderer._descendant_rows(child)


def render_html(html: bytes | str, width: int | None = None, color: bool | None = None) -> str:
    if isinstance(html, bytes):
        document = html.decode("utf-8", errors="replace")
    else:
        document = html
    return TerminalRenderer(width=width, color=color).render(document)
