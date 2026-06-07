# _meta/semantic/tests/test_health_check.py
import time

from health_check import (
    classify_recall_used,
    graphify_hint_followed,
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


def test_graphify_hint_followed():
    hint = {"type": "attachment", "attachment": {"type": "hook_additional_context",
            "content": ["Code graph available for this repo — graphify query"]}}
    followed = [hint, _tool("Bash", {"command": 'graphify query "what calls foo"'})]
    assert graphify_hint_followed(followed) == (1, 1)

    ignored = [hint, _tool("Bash", {"command": "grep -r foo ."})]
    assert graphify_hint_followed(ignored) == (1, 0)

    none = [_tool("Bash", {"command": "graphify query x"})]
    assert graphify_hint_followed(none) == (0, 0)


def test_within_window():
    now = time.time()
    assert within_window(now - 5 * 86400, 30)
    assert not within_window(now - 40 * 86400, 30)
