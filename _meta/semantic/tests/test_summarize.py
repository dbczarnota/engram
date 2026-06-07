from summarize import (
    ClaudeCliSummarizer, OllamaSummarizer,
    build_capture_prompt, build_summarizer, parse_capture_json, run_capture,
)


def test_parse_capture_json_fenced_plain_and_malformed():
    assert parse_capture_json('```json\n{"journal":"- x"}\n```')["journal"] == "- x"
    assert parse_capture_json('{"a":1}') == {"a": 1}
    assert parse_capture_json("not json") == {}
    assert parse_capture_json("[1,2]") == {}


def test_build_capture_prompt_reflects_lang_and_match():
    _, u = build_capture_prompt("fact-gate", "feat/x", "Polish")
    assert "Polish" in u and "UPDATE" in u and "fact-gate" in u
    _, u2 = build_capture_prompt("", "feat/new-thing", "English")
    assert "FEATURE" in u2 and "new-thing" in u2


class _Fake:
    name = "fake"
    last_usage = {"in": 0, "out": 0, "cost": 0.0}
    def __init__(self, out): self._out = out
    def generate(self, system, user): return self._out


def test_run_capture_roundtrip():
    out = '```json\n{"journal":"- did x","lesson":null,"feature":{"kind":"FEATURE","name":"y","body":"## What"}}\n```'
    d = run_capture(_Fake(out), "transcript", "", "feat/y", "English")
    assert d["journal"] == "- did x" and d["feature"]["name"] == "y" and d["lesson"] is None


def test_build_summarizer_selection(monkeypatch):
    monkeypatch.setenv("BRAIN_CAPTURE_PROVIDER", "ollama")
    monkeypatch.setenv("BRAIN_CAPTURE_MODEL", "qwen2.5")
    s = build_summarizer()
    assert isinstance(s, OllamaSummarizer) and s.name == "ollama:qwen2.5"
    monkeypatch.setenv("BRAIN_CAPTURE_PROVIDER", "claude-cli")
    monkeypatch.setenv("BRAIN_CAPTURE_MODEL", "")
    assert isinstance(build_summarizer(), ClaudeCliSummarizer)


def test_ollama_request_shaping(monkeypatch):
    import json as _j
    captured = {}
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return _j.dumps({"response": '{"journal":"- ok"}', "prompt_eval_count": 11, "eval_count": 7}).encode()
    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = _j.loads(req.data)
        return _Resp()
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    s = OllamaSummarizer("qwen2.5", "http://h:1")
    out = s.generate("sys", "usr")
    assert captured["url"] == "http://h:1/api/generate"
    assert captured["body"]["model"] == "qwen2.5" and captured["body"]["system"] == "sys"
    assert parse_capture_json(out)["journal"] == "- ok"
    assert s.last_usage == {"in": 11, "out": 7, "cost": 0.0}


def test_normalize_capture_journal_list_to_string():
    from summarize import normalize_capture
    assert normalize_capture({"journal": ["- a", "- b"]})["journal"] == "- a\n- b"
    assert normalize_capture({"journal": None})["journal"] == ""
    assert normalize_capture({"journal": "- x"})["journal"] == "- x"
    assert normalize_capture("nope") == {}


def test_claude_cli_envelope_and_usage(monkeypatch):
    from summarize import ClaudeCliSummarizer
    captured = {}
    monkeypatch.setattr("shutil.which", lambda name: r"C:\x\claude.CMD")
    envelope = (
        '{"result":"{\\"journal\\":\\"- ok\\"}",'
        '"usage":{"input_tokens":120,"output_tokens":30},"total_cost_usd":0.0042}'
    )
    class _R:
        stdout = envelope
    monkeypatch.setattr("subprocess.run", lambda args, **kw: captured.update(args=args) or _R())
    s = ClaudeCliSummarizer("sonnet")
    out = s.generate("sys", "usr")
    assert captured["args"][0].endswith("claude.CMD")
    assert "--output-format" in captured["args"] and "json" in captured["args"]
    assert "--model" in captured["args"] and "sonnet" in captured["args"]
    assert parse_capture_json(out)["journal"] == "- ok"  # inner result is the model's JSON answer
    assert s.last_usage == {"in": 120, "out": 30, "cost": 0.0042}


def test_log_usage_appends(tmp_path):
    from summarize import _log_usage
    _log_usage(tmp_path, "claude-cli:sonnet", {"in": 100, "out": 20, "cost": 0.003})
    import json as _j
    log = tmp_path / "_meta" / "state" / "capture-usage.jsonl"
    rec = _j.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["in"] == 100 and rec["out"] == 20 and rec["name"] == "claude-cli:sonnet" and "ts" in rec
