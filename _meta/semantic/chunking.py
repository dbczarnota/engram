from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")

_FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n?", re.DOTALL)


def strip_frontmatter(content: str) -> str:
    """Drop a leading YAML frontmatter block so it is never indexed or surfaced."""
    return _FRONTMATTER_RE.sub("", content, count=1)


@dataclass(frozen=True)
class Chunk:
    path: str  # vault-relative posix path
    heading_path: str  # "Title › Sub A" — "" before the first heading
    text: str  # body text under the heading (raw)
    content_hash: str  # sha256 of heading_path + body; path-independent


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _hash(heading_path: str, text: str) -> str:
    payload = f"{heading_path}\n\n{_normalize(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def chunk_markdown(path: str, content: str) -> list[Chunk]:
    """Split markdown into chunks at H1–H3 boundaries.

    H4+ stay as body inside the enclosing H1–H3 chunk. Content before the first
    heading becomes a chunk with heading_path "". Empty-body chunks are dropped.
    """
    content = strip_frontmatter(content)
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []  # (level, title) for current H1–H3 path
    body: list[str] = []

    def flush() -> None:
        heading_path = " › ".join(title for _, title in stack)
        text = "\n".join(body).strip()
        if text:
            chunks.append(Chunk(path, heading_path, text, _hash(heading_path, text)))

    for line in content.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            body = []
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2)))
        else:
            body.append(line)
    flush()
    return chunks


def embed_input(chunk: Chunk) -> str:
    """The text actually sent to the embedder: heading context + body."""
    if chunk.heading_path:
        return f"{chunk.heading_path}\n\n{chunk.text}"
    return chunk.text
