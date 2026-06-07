# _meta/semantic/tests/test_recall_log.py
import json
from pathlib import Path

from autorecall import _append_recall_log


def test_recall_log_line(tmp_path: Path):
    _append_recall_log(tmp_path, prompt="how do we do auth", paths=["standards/two-scheme-auth.md"], tier=2, score=0.7)
    log = tmp_path / "_meta" / "state" / "recall-log.jsonl"
    assert log.exists()
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["paths"] == ["standards/two-scheme-auth.md"]
    assert rec["tier"] == 2
    assert "prompt_hash" in rec and "prompt" not in rec  # privacy: hash only
