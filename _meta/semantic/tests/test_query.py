from pathlib import Path

import pytest

from fakes import FakeEmbedder
from index import build_index
from query import Hit, IndexMismatch, rrf, search


def test_rrf_combines_ranks():
    # chunk 2 appears high in both lists -> should win.
    fused = rrf([[1, 2, 3], [2, 5]], k=60)
    ids = [cid for cid, _ in fused]
    assert ids[0] == 2


def test_rrf_empty_lists():
    assert rrf([[], []], k=60) == []


def _vault(root: Path) -> None:
    (root / "standards").mkdir(parents=True)
    (root / "standards" / "auth.md").write_text(
        "# Two-scheme auth\n\nX-API-Key for clients, Kinde JWT for dashboards.\n",
        encoding="utf-8",
    )
    (root / "standards" / "deps.md").write_text(
        "# Dependencies\n\nPin floors to versions actually tested.\n", encoding="utf-8"
    )


def test_search_returns_hits(tmp_path, fake_embedder):
    _vault(tmp_path)
    build_index(tmp_path, fake_embedder)
    hits = search(tmp_path, "Kinde JWT dashboards", embedder=fake_embedder, top_n=5)
    assert hits and isinstance(hits[0], Hit)
    assert any("auth.md" in h.path for h in hits)


def test_search_fts_only_terms_still_work(tmp_path, fake_embedder):
    _vault(tmp_path)
    build_index(tmp_path, fake_embedder)
    hits = search(tmp_path, "floors tested", embedder=fake_embedder, top_n=5)
    assert any("deps.md" in h.path for h in hits)


def test_identity_mismatch_raises(tmp_path, fake_embedder):
    _vault(tmp_path)
    build_index(tmp_path, fake_embedder)
    other = FakeEmbedder(dim=8, name="other@8")
    with pytest.raises(IndexMismatch):
        search(tmp_path, "anything", embedder=other)
