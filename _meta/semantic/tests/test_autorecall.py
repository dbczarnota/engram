from pathlib import Path

from fakes import FakeEmbedder
from index import build_index
from autorecall import auto_recall, is_substantive, load_config


def _vault(root: Path) -> None:
    (root / "standards").mkdir(parents=True)
    (root / "standards" / "auth.md").write_text(
        "# Two-scheme auth\n\nX-API-Key for clients, Kinde JWT for dashboards.\n", encoding="utf-8"
    )
    (root / "projects" / "x").mkdir(parents=True)
    (root / "projects" / "x" / "journal.md").write_text(
        "# Journal\n\nKinde JWT dashboards work done today.\n", encoding="utf-8"
    )


def test_is_substantive():
    assert not is_substantive("ok")
    assert not is_substantive("run it")
    assert is_substantive("how do we authenticate dashboard clients")  # length
    assert is_substantive("auth?")  # question mark
    assert is_substantive("jak robimy auth")  # cue 'jak'


def test_fts_hit_in_scope_surfaces_without_embedder(tmp_path):
    _vault(tmp_path)
    build_index(tmp_path, FakeEmbedder())

    class Boom:
        name = "boom@8"
        dim = 8

        def embed_documents(self, t):
            raise AssertionError("genai path used")

        def embed_query(self, t):
            raise AssertionError("genai path used")

    hint = auto_recall(
        tmp_path,
        "how do we handle Kinde JWT for dashboard clients",
        top_n=3,
        min_score=0.3,
        token_budget=200,
        scope=["standards", "lessons", "decisions"],
        embedder=Boom(),
    )
    assert hint and "standards/auth.md" in hint
    assert "journal.md" not in hint  # journal is out of scope


class _StubToTarget:
    """Maps any query to the FakeEmbedder vector of a fixed target text (forces a semantic hit)."""

    name = "fake@8"
    dim = 8

    def __init__(self, target_text: str) -> None:
        self._target = target_text
        self.query_calls = 0

    def embed_documents(self, texts):
        return FakeEmbedder().embed_documents(texts)

    def embed_query(self, text):
        self.query_calls += 1
        return FakeEmbedder().embed_documents([self._target])[0]


def test_semantic_escalation_when_fts_empty(tmp_path):
    _vault(tmp_path)
    build_index(tmp_path, FakeEmbedder())
    # No word overlap with any note -> FTS empty -> escalation fires. Stub maps the query to the
    # auth chunk's embedding (embed_input = heading + body) so cosine == 1.0.
    target = "Two-scheme auth\n\nX-API-Key for clients, Kinde JWT for dashboards."
    stub = _StubToTarget(target)
    hint = auto_recall(
        tmp_path,
        "describe our overall credential handling philosophy please",
        top_n=3,
        min_score=0.5,
        token_budget=200,
        scope=["standards", "lessons", "decisions"],
        embedder=stub,
    )
    assert stub.query_calls == 1  # escalation actually happened
    assert hint and "standards/auth.md" in hint


def test_unrelated_substantive_prompt_is_silent(tmp_path):
    _vault(tmp_path)
    build_index(tmp_path, FakeEmbedder())
    hint = auto_recall(
        tmp_path,
        "explain quantum chromodynamics in great detail please",
        top_n=3,
        min_score=0.99,
        token_budget=200,
        scope=["standards", "lessons", "decisions"],
        embedder=FakeEmbedder(),
    )
    assert hint is None


def _recall(tmp_path, prompt, session_id):
    return auto_recall(
        tmp_path, prompt, top_n=3, min_score=0.3, token_budget=200,
        scope=["standards", "lessons", "decisions"], session_id=session_id, embedder=FakeEmbedder(),
    )


def test_session_dedupe(tmp_path):
    _vault(tmp_path)
    build_index(tmp_path, FakeEmbedder())
    prompt = "how do we handle Kinde JWT for dashboard clients"
    first = _recall(tmp_path, prompt, "s1")
    assert first and "standards/auth.md" in first
    second = _recall(tmp_path, prompt, "s1")
    assert second is None  # already surfaced this session
    third = _recall(tmp_path, prompt, "s2")  # a different session still gets it
    assert third and "standards/auth.md" in third


def test_load_config_defaults_and_override(tmp_path):
    cfg = load_config(tmp_path)  # no file -> defaults
    assert cfg["enabled"] is True and cfg["topN"] == 3 and "standards" in cfg["scope"]
    (tmp_path / "_meta").mkdir()
    (tmp_path / "_meta" / "engram.json").write_text(
        '{ "autoRecall": { "topN": 1, "scope": ["lessons"] } }', encoding="utf-8"
    )
    cfg2 = load_config(tmp_path)
    assert cfg2["topN"] == 1 and cfg2["scope"] == ["lessons"] and cfg2["enabled"] is True


def test_trivial_prompt_is_silent(tmp_path):
    _vault(tmp_path)
    build_index(tmp_path, FakeEmbedder())
    assert (
        auto_recall(
            tmp_path,
            "ok",
            top_n=3,
            min_score=0.3,
            token_budget=200,
            scope=["standards"],
            embedder=FakeEmbedder(),
        )
        is None
    )
