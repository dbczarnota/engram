# _meta/semantic/tests/test_health_check.py
import time

from health_check import (
    classify_recall_used,
    is_frontmatter_junk,
    within_window,
)


def _tool(name, inp):
    return {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": inp}]}}


def test_is_frontmatter_junk():
    assert is_frontmatter_junk("--- type: standard tags: [x]")
    assert is_frontmatter_junk("type: lesson")
    assert not is_frontmatter_junk("Put blobs behind a Protocol.")


def test_classify_recall_used_detects_later_read():
    entries = [_tool("Read", {"file_path": "C:/brain/standards/agents.md"})]
    assert classify_recall_used(entries, -1, ["standards/agents.md"]) is True
    assert classify_recall_used(entries, -1, ["lessons/kinde.md"]) is False
    assert classify_recall_used(entries, -1, []) is False


def test_within_window():
    now = time.time()
    assert within_window(now - 5 * 86400, 30)
    assert not within_window(now - 40 * 86400, 30)


def test_capture_usage_window(tmp_path):
    import datetime
    import json

    from health_check import capture_usage
    d = tmp_path / "_meta" / "state"
    d.mkdir(parents=True)
    now = datetime.datetime.now()
    old = (now - datetime.timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%S")
    recent = (now - datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
    lines = [
        json.dumps({"ts": recent, "name": "x", "in": 100, "out": 20, "cost": 0.01}),
        json.dumps({"ts": recent, "name": "x", "in": 50, "out": 10, "cost": 0.005}),
        json.dumps({"ts": old, "name": "x", "in": 999, "out": 999, "cost": 9.9}),
    ]
    (d / "capture-usage.jsonl").write_text("\n".join(lines), encoding="utf-8")
    t = capture_usage(tmp_path, 30)
    assert t["calls"] == 2 and t["in_tok"] == 150 and t["out_tok"] == 30
    assert round(t["cost"], 3) == 0.015
