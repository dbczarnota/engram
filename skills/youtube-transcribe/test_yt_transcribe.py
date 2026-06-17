"""Unit tests for yt_transcribe — mocked HTTP, no network, no real key."""

from __future__ import annotations

import json

import pytest

import yt_transcribe as yt


# --------------------------------------------------------------------------- #
# fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    """Point env-file and cache at tmp; provide a key via env var."""
    monkeypatch.setenv("STREAM2LLM_ENV_FILE", str(tmp_path / "stream2llm.env"))
    monkeypatch.setenv("STREAM2LLM_CACHE_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("STREAM2LLM_API_KEY", "str_testkey")
    monkeypatch.setenv("STREAM2LLM_BASE_URL", "https://api.test")


class FakeTransport:
    """Scripted transport: maps (method, path-suffix) -> (status, obj)."""

    def __init__(self, routes: dict, record: list | None = None):
        self.routes = routes
        self.record = record if record is not None else []

    def __call__(self, method, url, headers, body):
        self.record.append((method, url, headers, body))
        path = url.split("https://api.test", 1)[-1]
        for (m, suffix), (status, obj) in self.routes.items():
            if m == method and path.startswith(suffix):
                raw = json.dumps(obj).encode() if obj is not None else b""
                return status, raw
        return 404, b'{"detail":"no route"}'


def cfg():
    return yt.load_config()


# --------------------------------------------------------------------------- #
# parse_video_id
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=H9BUkgDf5Y4", "H9BUkgDf5Y4"),
        ("https://youtu.be/H9BUkgDf5Y4", "H9BUkgDf5Y4"),
        ("https://www.youtube.com/watch?v=H9BUkgDf5Y4&t=30s", "H9BUkgDf5Y4"),
        ("https://m.youtube.com/shorts/H9BUkgDf5Y4", "H9BUkgDf5Y4"),
        ("https://www.youtube.com/live/H9BUkgDf5Y4", "H9BUkgDf5Y4"),
        ("https://www.youtube.com/embed/H9BUkgDf5Y4", "H9BUkgDf5Y4"),
        ("H9BUkgDf5Y4", "H9BUkgDf5Y4"),
        ("https://example.com/watch?v=H9BUkgDf5Y4", None),
        ("https://www.youtube.com/watch?v=short", None),
    ],
)
def test_parse_video_id(url, expected):
    assert yt.parse_video_id(url) == expected


# --------------------------------------------------------------------------- #
# config + env parsing
# --------------------------------------------------------------------------- #


def test_parse_env_file_ignores_comments_and_quotes():
    text = '# c\nSTREAM2LLM_API_KEY="str_abc"\nSTREAM2LLM_BASE_URL=https://x\n\n'
    vals = yt.parse_env_file(text)
    assert vals["STREAM2LLM_API_KEY"] == "str_abc"
    assert vals["STREAM2LLM_BASE_URL"] == "https://x"


def test_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("STREAM2LLM_ENV_FILE", str(tmp_path / "nope.env"))
    monkeypatch.delenv("STREAM2LLM_API_KEY", raising=False)
    with pytest.raises(yt.TranscribeError, match="No STREAM2LLM_API_KEY"):
        yt.load_config()


def test_env_file_used_when_no_env_var(tmp_path, monkeypatch):
    (tmp_path / "s.env").write_text("STREAM2LLM_API_KEY=str_fromfile\n", encoding="utf-8")
    monkeypatch.setenv("STREAM2LLM_ENV_FILE", str(tmp_path / "s.env"))
    monkeypatch.delenv("STREAM2LLM_API_KEY", raising=False)
    monkeypatch.delenv("STREAM2LLM_BASE_URL", raising=False)
    c = yt.load_config()
    assert c.api_key == "str_fromfile"
    assert c.base_url == yt.DEFAULT_BASE_URL


# --------------------------------------------------------------------------- #
# submit
# --------------------------------------------------------------------------- #


def test_submit_posts_and_caches():
    record: list = []
    t = FakeTransport(
        {("POST", "/v2/youtube/items"): (201, {"id": "sub-123", "status": "active"})}, record
    )
    out = yt.submit("https://youtu.be/H9BUkgDf5Y4", "pl", cfg(), t)
    assert out == {
        "subscription_id": "sub-123",
        "video_id": "H9BUkgDf5Y4",
        "status": "active",
        "mode": "quick",
    }
    # key sent, transcript requested, browser-ish UA to clear Cloudflare
    _, _, headers, body = record[0]
    assert headers["X-API-Key"] == "str_testkey"
    assert "Mozilla" in headers["User-Agent"]
    payload = json.loads(body)
    assert payload["include_transcript"] is True
    # default is the quick path: prefer existing subtitles
    assert payload["prefer_youtube_subtitles"] is True
    # cached under the quick mode key
    assert yt.load_cache()["H9BUkgDf5Y4:quick"]["subscription_id"] == "sub-123"


def test_submit_deep_sets_prefer_false_and_caches_under_deep():
    record: list = []
    t = FakeTransport(
        {("POST", "/v2/youtube/items"): (201, {"id": "sub-deep", "status": "active"})}, record
    )
    out = yt.submit("https://youtu.be/H9BUkgDf5Y4", "pl", cfg(), t, deep=True)
    assert out["mode"] == "deep"
    assert json.loads(record[0][3])["prefer_youtube_subtitles"] is False
    cache = yt.load_cache()
    assert cache["H9BUkgDf5Y4:deep"]["subscription_id"] == "sub-deep"
    assert "H9BUkgDf5Y4:quick" not in cache


def test_submit_401_is_clear():
    t = FakeTransport({("POST", "/v2/youtube/items"): (401, {"detail": "bad key"})})
    with pytest.raises(yt.TranscribeError, match="401"):
        yt.submit("https://youtu.be/H9BUkgDf5Y4", "pl", cfg(), t)


def test_submit_400_surfaces_detail():
    t = FakeTransport(
        {("POST", "/v2/youtube/items"): (400, {"detail": "Broadcast not live yet / not processable"})}
    )
    with pytest.raises(yt.TranscribeError, match="not processable"):
        yt.submit("https://youtu.be/H9BUkgDf5Y4", "pl", cfg(), t)


def test_submit_rejects_non_youtube():
    with pytest.raises(yt.TranscribeError, match="youtube"):
        yt.submit("https://vimeo.com/123", "pl", cfg(), FakeTransport({}))


# --------------------------------------------------------------------------- #
# assemble_transcript / render_digest
# --------------------------------------------------------------------------- #


def test_assemble_transcript_orders_by_start():
    results = [
        {"chunk_start": 180, "raw_transcript": "second"},
        {"chunk_start": 0, "raw_transcript": "first"},
        {"chunk_start": 360, "raw_transcript": ""},
    ]
    assert yt.assemble_transcript(results) == "first\nsecond"


def test_render_digest_flattens_stories():
    digests = [
        {"payload": {"stories": [{"title": "T", "summary": "S", "is_news": True, "facts": [{"text": "f1"}]}]}}
    ]
    out = yt.render_digest(digests)
    assert out == [{"title": "T", "summary": "S", "is_news": True, "facts": ["f1"]}]


# --------------------------------------------------------------------------- #
# fetch
# --------------------------------------------------------------------------- #


def test_fetch_still_active_reports_progress():
    yt.save_cache({"H9BUkgDf5Y4:quick": {"subscription_id": "sub-1", "status": "active"}})
    t = FakeTransport(
        {
            ("GET", "/v2/streams/subscriptions/sub-1/results"): (200, [{"chunk_id": "c1", "chunk_start": 0}]),
            ("GET", "/v2/streams/subscriptions/sub-1"): (200, {"status": "active"}),
        }
    )
    out = yt.fetch("https://youtu.be/H9BUkgDf5Y4", cfg(), t)
    assert out == {"status": "active", "subscription_id": "sub-1", "chunks_so_far": 1}


def test_fetch_completed_assembles_transcript_and_digest():
    yt.save_cache({"H9BUkgDf5Y4:quick": {"subscription_id": "sub-9", "status": "active"}})
    t = FakeTransport(
        {
            ("GET", "/v2/streams/subscriptions/sub-9/results"): (
                200,
                [
                    {"chunk_id": "c1", "chunk_start": 0, "chunk_end": 180, "raw_transcript": "hello"},
                    {"chunk_id": "c2", "chunk_start": 180, "chunk_end": 300, "raw_transcript": "world"},
                ],
            ),
            ("GET", "/v2/streams/subscriptions/sub-9/digests"): (
                200,
                [{"payload": {"stories": [{"title": "T", "summary": "S"}]}}],
            ),
            ("GET", "/v2/streams/subscriptions/sub-9"): (200, {"status": "completed"}),
        }
    )
    out = yt.fetch("https://youtu.be/H9BUkgDf5Y4", cfg(), t)
    assert out["status"] == "completed"
    assert out["transcript"] == "hello\nworld"
    assert out["chunk_count"] == 2
    assert out["duration_s"] == 300
    assert out["digest"][0]["title"] == "T"


def test_fetch_failed_raises():
    yt.save_cache({"H9BUkgDf5Y4:quick": {"subscription_id": "sub-x", "status": "active"}})
    t = FakeTransport(
        {
            ("GET", "/v2/streams/subscriptions/sub-x/results"): (200, []),
            ("GET", "/v2/streams/subscriptions/sub-x"): (200, {"status": "failed"}),
        }
    )
    with pytest.raises(yt.TranscribeError, match="failed"):
        yt.fetch("https://youtu.be/H9BUkgDf5Y4", cfg(), t)


def test_fetch_unknown_video_needs_submit():
    with pytest.raises(yt.TranscribeError, match="submit"):
        yt.fetch("https://youtu.be/H9BUkgDf5Y4", cfg(), FakeTransport({}))


# --------------------------------------------------------------------------- #
# get (submit-or-fetch)
# --------------------------------------------------------------------------- #


def test_get_submits_on_cache_miss():
    t = FakeTransport({("POST", "/v2/youtube/items"): (201, {"id": "sub-new", "status": "active"})})
    out = yt.get("https://youtu.be/H9BUkgDf5Y4", "pl", cfg(), t)
    assert out["subscription_id"] == "sub-new"


def test_get_fetches_on_cache_hit():
    yt.save_cache({"H9BUkgDf5Y4:quick": {"subscription_id": "sub-hit", "status": "active"}})
    t = FakeTransport(
        {
            ("GET", "/v2/streams/subscriptions/sub-hit/results"): (200, []),
            ("GET", "/v2/streams/subscriptions/sub-hit"): (200, {"status": "active"}),
        }
    )
    out = yt.get("https://youtu.be/H9BUkgDf5Y4", "pl", cfg(), t)
    assert out["subscription_id"] == "sub-hit"
    assert out["status"] == "active"


def test_get_quick_then_deep_resubmits():
    """A deep request after a quick one is a cache miss → new (full-audio) job."""
    yt.save_cache({"H9BUkgDf5Y4:quick": {"subscription_id": "sub-quick", "status": "completed"}})
    record: list = []
    t = FakeTransport(
        {("POST", "/v2/youtube/items"): (201, {"id": "sub-deep", "status": "active"})}, record
    )
    out = yt.get("https://youtu.be/H9BUkgDf5Y4", "pl", cfg(), t, deep=True)
    # submitted a fresh deep job rather than returning the cached quick one
    assert out["subscription_id"] == "sub-deep"
    assert out["mode"] == "deep"
    assert record and record[0][0] == "POST"
    assert json.loads(record[0][3])["prefer_youtube_subtitles"] is False


# --------------------------------------------------------------------------- #
# main / CLI
# --------------------------------------------------------------------------- #


def test_main_submit_prints_json(capsys):
    t = FakeTransport({("POST", "/v2/youtube/items"): (201, {"id": "sub-cli", "status": "active"})})
    rc = yt.main(["submit", "https://youtu.be/H9BUkgDf5Y4"], transport=t)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["subscription_id"] == "sub-cli"


def test_main_deep_flag_sets_prefer_false(capsys):
    record: list = []
    t = FakeTransport(
        {("POST", "/v2/youtube/items"): (201, {"id": "sub-d", "status": "active"})}, record
    )
    rc = yt.main(["submit", "https://youtu.be/H9BUkgDf5Y4", "--deep"], transport=t)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "deep"
    assert json.loads(record[0][3])["prefer_youtube_subtitles"] is False


def test_main_error_returns_1_and_no_key_leak(capsys):
    t = FakeTransport({("POST", "/v2/youtube/items"): (401, {"detail": "bad"})})
    rc = yt.main(["submit", "https://youtu.be/H9BUkgDf5Y4"], transport=t)
    assert rc == 1
    out = capsys.readouterr().out
    assert "error" in json.loads(out)
    assert "str_testkey" not in out
