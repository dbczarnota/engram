from __future__ import annotations

import reverify


class _Cfg:
    def __init__(self, verify, setup=None):
        self.verify = verify
        self.setup = setup or {}


def test_verify_green_true_when_no_failures(monkeypatch, tmp_path):
    from baseline import CommandResult
    monkeypatch.setattr(reverify.baseline, "run_verify_detailed",
                        lambda cfg, wt, **k: [CommandResult("test", "pytest", 0, "1 passed")])
    green, _ = reverify.verify_green(_Cfg({"test": "pytest"}), tmp_path)
    assert green is True


def test_verify_green_false_on_a_failure(monkeypatch, tmp_path):
    from baseline import CommandResult
    monkeypatch.setattr(reverify.baseline, "run_verify_detailed",
                        lambda cfg, wt, **k: [CommandResult("test", "pytest", 1, "FAILED t.py::x - boom")])
    green, detail = reverify.verify_green(_Cfg({"test": "pytest"}), tmp_path)
    assert green is False and "x" in detail


def test_setup_bundle_resolves_strong_path_and_runs_setup(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(reverify.baseline, "docker_available", lambda: True)
    monkeypatch.setattr(reverify.baseline, "run_setup",
                        lambda cfg, wt: seen.update(verify=dict(cfg.verify)) or (True, "ok"))
    cfg = _Cfg({"test": {"requires": "docker", "with": "uv run pytest", "without": "pytest -m no"}},
               setup={"deps": "uv sync"})
    ok, _ = reverify.setup_bundle(cfg, tmp_path)
    assert ok is True
    assert cfg.verify["test"] == "uv run pytest"   # resolved to the strong path (docker up)
