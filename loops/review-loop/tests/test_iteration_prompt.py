from __future__ import annotations

from pathlib import Path

PROMPT = Path(__file__).resolve().parent.parent / "iteration_prompt.md"


def test_prompt_declares_schema_findings_contract():
    text = PROMPT.read_text(encoding="utf-8")
    for key in ("fingerprint", "summary", "findings", "dimension"):
        assert key in text
    # the per-dimension scope (incl. the correctness-bug focus) is injected via this placeholder
    # (filled by _build_prompt); test_build_prompt asserts the built prompt's correctness-bug focus.
    assert "{DIMENSIONS}" in text


def test_prompt_is_a_direct_task_not_loop_framed():
    # The "review loop / iteration / dimension" framing made the agent confabulate an
    # orchestration instead of doing the review — keep the prompt a direct task.
    lower = PROMPT.read_text(encoding="utf-8").lower()
    for meta in ("iteration of", "review loop", "dimension:"):
        assert meta not in lower
