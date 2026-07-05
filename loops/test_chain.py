from __future__ import annotations

from pathlib import Path

import chain


class _R:
    def __init__(self, code=0):
        self.returncode = code


def _fake(calls, codes=None):
    codes = codes or {}

    def run_loop(loop, repo, extra):
        calls.append((loop, list(extra)))
        return _R(codes.get(loop, 0))

    return run_loop


def test_runs_three_stages_in_order_and_never_touches_registry(tmp_path):
    reg = tmp_path / "bug-registry.md"
    reg.write_text("SEED-QUEUE", encoding="utf-8")   # prove the chain itself never resets/writes it
    calls = []
    codes = chain.run_chain(tmp_path, max_fixes=3, run_loop=_fake(calls))
    assert [c[0] for c in calls] == ["review-loop", "fix-loop", "integrate-loop"]
    assert calls[1][1] == ["--max-fixes", "3"]        # fix stage is budgeted
    assert reg.read_text(encoding="utf-8") == "SEED-QUEUE"   # untouched -> upsert semantics preserved
    assert codes == {"review": 0, "fix": 0, "integrate": 0}


def test_no_max_fixes_passes_no_budget_flag(tmp_path):
    calls = []
    chain.run_chain(tmp_path, run_loop=_fake(calls))
    assert calls[1] == ("fix-loop", [])               # no --max-fixes when unbounded


def test_review_failure_stops_before_fix_and_integrate(tmp_path):
    calls = []
    codes = chain.run_chain(tmp_path, run_loop=_fake(calls, {"review-loop": 2}))
    assert [c[0] for c in calls] == ["review-loop"]   # fix + integrate never ran
    assert codes == {"review": 2}


def test_fix_failure_stops_before_integrate(tmp_path):
    calls = []
    codes = chain.run_chain(tmp_path, max_fixes=5, run_loop=_fake(calls, {"fix-loop": 1}))
    assert [c[0] for c in calls] == ["review-loop", "fix-loop"]
    assert "integrate" not in codes


def test_default_run_loop_targets_the_loop_dir():
    # sanity: the real runner would invoke `python loops/<loop> <repo>`
    assert (Path(chain.__file__).resolve().parent / "fix-loop" / "__main__.py").is_file()
