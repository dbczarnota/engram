from __future__ import annotations

from config import ReviewLoopConfig
from gating import enabled_dimensions


def _cfg(**kw) -> ReviewLoopConfig:
    base = dict(verify={"test": "pytest"}, report_dir="r", max_iter=1, budget_tokens=1)
    base.update(kw)
    return ReviewLoopConfig(**base)


def test_log_sweep_requires_logfire():
    assert "log-sweep" not in enabled_dimensions(_cfg(logfire=None))
    assert "log-sweep" in enabled_dimensions(_cfg(logfire="hf"))


def test_bug_hunt_always_enabled():
    assert "bug-hunt" in enabled_dimensions(_cfg())


def test_enabled_layers_backend_and_frontend():
    from gating import enabled_layers
    cfg = ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1,
                           backend=["backend/**"], frontend=["frontend/**"])
    assert enabled_layers(cfg) == [("backend", ["backend/**"]), ("frontend", ["frontend/**"])]


def test_enabled_layers_backend_only_when_no_frontend():
    from gating import enabled_layers
    cfg = ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1,
                           backend=["src/**"], frontend=[])
    assert enabled_layers(cfg) == [("backend", ["src/**"])]


def test_enabled_layers_all_when_neither_configured():
    from gating import enabled_layers
    cfg = ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1)
    assert enabled_layers(cfg) == [("all", [])]
