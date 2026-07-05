from __future__ import annotations

from claude_iterate import _build_prompt
from config import ReviewLoopConfig


def _cfg(verify: dict[str, str]) -> ReviewLoopConfig:
    return ReviewLoopConfig(
        verify=verify,
        report_dir="reports",
        max_iter=2,
        budget_tokens=1000,
        backend=["src/**"],
    )


def test_build_prompt_fills_placeholders():
    prompt = _build_prompt(_cfg({"test": "pytest"}), "backend", ["src/**"])
    for token in ("{PATHS}", "{LAYER}", "{DIMENSIONS}"):
        assert token not in prompt
    assert "src/**" in prompt        # PATHS filled
    assert "backend" in prompt       # LAYER filled


def test_build_prompt_lists_all_code_dimensions():
    prompt = _build_prompt(_cfg({"test": "pytest"}), "backend", ["src/**"])
    for dim in ("bug-hunt", "security", "dead-code", "dedup", "complexity", "perf", "consistency"):
        assert dim in prompt
    assert "{DIMENSIONS}" not in prompt  # placeholder filled


def test_build_prompt_keeps_correctness_bug_focus():
    # The correctness-bug scope moved from the static template into the injected dimension
    # catalog; assert it survives in the BUILT prompt (what the agent actually receives).
    prompt = _build_prompt(_cfg({"test": "pytest"}), "backend", ["src/**"])
    assert "correctness bug" in prompt.lower()


def test_build_prompt_single_dimension_only():
    from claude_iterate import _PROMPT_DIMENSIONS
    security = [d for d in _PROMPT_DIMENSIONS if d[0] == "security"]
    prompt = _build_prompt(_cfg({"test": "pytest"}), "backend", ["src/**"], security)
    assert "- **security**" in prompt
    assert "- **perf**" not in prompt          # other dimensions' block lines absent
    assert "- **dead-code**" not in prompt
