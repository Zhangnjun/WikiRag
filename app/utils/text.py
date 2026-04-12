from __future__ import annotations

import re
from collections import Counter

from bs4 import BeautifulSoup, NavigableString, Tag


TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff]{2,}")
WHITESPACE_RE = re.compile(r"\s+")
PENDING = "待补充"


def clean_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", (text or "").replace("\xa0", " ")).strip()


def split_lines(text: str) -> list[str]:
    return [clean_text(line) for line in (text or "").splitlines() if clean_text(line)]


def tokenize(text: str) -> list[str]:
    return [match.group(0) for match in TOKEN_RE.finditer(text or "")]


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    stop_words = {
        "待补充",
        "以及",
        "进行",
        "需要",
        "通过",
        "这个",
        "可以",
        "如果",
        "处理",
        "步骤",
        "说明",
        "使用",
    }
    tokens = [token for token in tokenize(text) if len(token) >= 2 and token not in stop_words]
    counter = Counter(tokens)
    return [token for token, _ in counter.most_common(limit)]


def html_to_markdownish(raw_html: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(raw_html or "", "html.parser")
    images: list[str] = []
    for image in soup.find_all("img"):
        src = image.get("src")
        if src:
            images.append(src)
        image.decompose()
    lines: list[str] = []
    for node in soup.contents:
        _walk_html(node, lines)
    rendered = "\n".join(_normalize_lines(lines)).strip()
    return rendered, images


def _walk_html(node: object, lines: list[str]) -> None:
    if isinstance(node, NavigableString):
        text = clean_text(str(node))
        if text:
            lines.append(text)
        return
    if not isinstance(node, Tag):
        return
    name = node.name.lower()
    if name in {"script", "style"}:
        return
    if name in {"h1", "h2", "h3", "h4"}:
        level = int(name[1])
        text = clean_text(node.get_text(" ", strip=True))
        if text:
            lines.append(f"{'#' * level} {text}")
        return
    if name == "li":
        text = clean_text(node.get_text(" ", strip=True))
        if text:
            lines.append(f"- {text}")
        return
    if name == "table":
        lines.append("[table]")
        for row in node.find_all("tr"):
            cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            if cells:
                lines.append("| " + " | ".join(cells) + " |")
        return
    if name == "br":
        lines.append("")
        return
    for child in node.children:
        _walk_html(child, lines)


def _normalize_lines(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    previous_blank = False
    for line in lines:
        clean = clean_text(line)
        if not clean:
            if not previous_blank:
                normalized.append("")
            previous_blank = True
            continue
        normalized.append(clean)
        previous_blank = False
    return normalized
