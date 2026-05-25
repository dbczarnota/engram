from __future__ import annotations

import math
import os
from collections.abc import Iterator
from typing import Protocol, runtime_checkable

_GEMINI_MAX_BATCH = 100  # BatchEmbedContentsRequest caps at 100 requests per call


def _batches(seq: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


@runtime_checkable
class Embedder(Protocol):
    name: str  # identity, e.g. "gemini:gemini-embedding-001@768"
    dim: int  # vector dimensionality; fixed for the vec0 table

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class GeminiEmbedder:
    """Gemini embeddings via google-genai. Truncated (<3072) dims are L2-normalized
    as Google recommends for gemini-embedding-001."""

    def __init__(
        self,
        model: str = "gemini-embedding-001",
        dim: int = 768,
        api_key: str | None = None,
    ) -> None:
        from google import genai

        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY to use the Gemini embedder.")
        self._client = genai.Client(api_key=key)
        self.model = model
        self.dim = dim
        self.name = f"gemini:{model}@{dim}"

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        from google.genai import types

        cfg = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dim)
        out: list[list[float]] = []
        for batch in _batches(texts, _GEMINI_MAX_BATCH):
            resp = self._client.models.embed_content(model=self.model, contents=batch, config=cfg)
            out.extend(l2_normalize(list(e.values or [])) for e in (resp.embeddings or []))
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


def build_embedder() -> Embedder:
    """Select the embedding provider from env. Gemini is the only one for now;
    Voyage/Jina drop in here without touching callers (spec §5.1)."""
    provider = os.environ.get("BRAIN_EMBED_PROVIDER", "gemini")
    model = os.environ.get("BRAIN_EMBED_MODEL", "gemini-embedding-001")
    dim = int(os.environ.get("BRAIN_EMBED_DIM", "768"))
    if provider == "gemini":
        return GeminiEmbedder(model=model, dim=dim)
    raise ValueError(f"Unknown embedder provider: {provider!r}")
