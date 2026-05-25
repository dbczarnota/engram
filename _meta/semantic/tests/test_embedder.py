import math

from embedder import Embedder, _batches, build_embedder, l2_normalize


def test_batches_splits_by_size():
    items = [str(i) for i in range(250)]
    assert [len(b) for b in _batches(items, 100)] == [100, 100, 50]


def test_batches_empty():
    assert list(_batches([], 100)) == []


def test_l2_normalize_unit_length():
    v = l2_normalize([3.0, 4.0])
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)


def test_l2_normalize_zero_vector_safe():
    assert l2_normalize([0.0, 0.0]) == [0.0, 0.0]


def test_fake_embedder_satisfies_protocol(fake_embedder):
    assert isinstance(fake_embedder, Embedder)
    docs = fake_embedder.embed_documents(["a", "b"])
    assert len(docs) == 2 and len(docs[0]) == fake_embedder.dim


def test_build_embedder_unknown_provider(monkeypatch):
    monkeypatch.setenv("BRAIN_EMBED_PROVIDER", "nope")
    try:
        build_embedder()
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "nope" in str(exc)


def test_build_embedder_gemini_requires_key(monkeypatch):
    monkeypatch.setenv("BRAIN_EMBED_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    try:
        build_embedder()
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "GEMINI_API_KEY" in str(exc)
