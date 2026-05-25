from __future__ import annotations

import hashlib

from embedder import l2_normalize


class FakeEmbedder:
    """Deterministic, offline embedder for tests. dim is small."""

    def __init__(self, dim: int = 8, name: str = "fake@8") -> None:
        self.dim = dim
        self.name = name

    def _vec(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [h[i % len(h)] / 255.0 for i in range(self.dim)]
        return l2_normalize(raw)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)
