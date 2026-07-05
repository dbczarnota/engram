from __future__ import annotations

from pathlib import Path

from gate import blast_radius_ok, gate_fix


def _finding(dimension="dedup", summary="dup"):
    from report import Finding
    return Finding(fingerprint="x:1", file="a.py", line=1, dimension=dimension,
                   severity="low", layer="backend", summary=summary)


def test_blast_radius_rejects_too_many_files():
    ok, why = blast_radius_ok([f"f{i}.py" for i in range(6)], max_files=5)
    assert ok is False and "files" in why.lower()


def test_blast_radius_rejects_migration_or_deploy():
    ok, why = blast_radius_ok(["backend/alembic/versions/abc.py"])
    assert ok is False and "migration" in why.lower()
    ok2, _ = blast_radius_ok(["k8s/backend-deploy.yaml"])
    assert ok2 is False


def test_blast_radius_ok_for_small_code_change():
    ok, why = blast_radius_ok(["backend/api/streams.py"])
    assert ok is True


def test_gate_passes_when_blast_verify_and_skeptic_all_ok():
    ok, why, _tok = gate_fix(cfg=object(), worktree=Path("."), finding=_finding(),
                       changed=["a.py"],
                       run_verify=lambda cfg, wt: (True, "green"),
                       skeptic=lambda f, wt: ("confirmed", "good fix", 10))
    assert ok is True


def test_gate_fails_when_verify_red():
    ok, why, _tok = gate_fix(cfg=object(), worktree=Path("."), finding=_finding(),
                       changed=["a.py"],
                       run_verify=lambda cfg, wt: (False, "FAILED test_x"),
                       skeptic=lambda f, wt: ("confirmed", "ok", 0))
    assert ok is False and "verify" in why.lower()


def test_gate_fails_when_skeptic_refutes():
    ok, why, _tok = gate_fix(cfg=object(), worktree=Path("."), finding=_finding(),
                       changed=["a.py"],
                       run_verify=lambda cfg, wt: (True, "green"),
                       skeptic=lambda f, wt: ("refuted", "did not address the finding", 5))
    assert ok is False and "refut" in why.lower()


def test_gate_fails_when_no_change():
    ok, why, _tok = gate_fix(cfg=object(), worktree=Path("."), finding=_finding(),
                       changed=[], run_verify=lambda cfg, wt: (True, "green"),
                       skeptic=lambda f, wt: ("confirmed", "ok", 0))
    assert ok is False and "no change" in why.lower()
