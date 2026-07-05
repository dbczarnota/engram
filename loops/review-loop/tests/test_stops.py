from __future__ import annotations

from stops import StopController


def test_max_iter_stop():
    sc = StopController(max_iter=2, budget_tokens=10_000)
    assert sc.check(1, 100, {"a"}) == (True, "")
    assert sc.check(2, 200, {"b"}) == (False, "max_iter")


def test_budget_stop():
    sc = StopController(max_iter=9, budget_tokens=500)
    assert sc.check(1, 600, {"a"}) == (False, "budget")


def test_clean_pass_stop():
    sc = StopController(max_iter=9, budget_tokens=10_000)
    assert sc.check(1, 10, set()) == (False, "clean")


def test_stagnation_stop():
    sc = StopController(max_iter=9, budget_tokens=10_000, stagnation_limit=2)
    assert sc.check(1, 10, {"x"}) == (True, "")
    # same fingerprint reappears -> seen twice -> stagnation
    assert sc.check(2, 20, {"x"}) == (False, "stagnation")
