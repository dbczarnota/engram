from __future__ import annotations

from pathlib import Path

# Paths a refactor fix must not touch (behavior/infra-critical) — reject the fix if it does.
_FORBIDDEN_MARKERS = ("alembic/versions/", "/migrations/", "k8s/", "deploy", ".github/", "dockerfile")


def blast_radius_ok(files: list[str], *, max_files: int = 5) -> tuple[bool, str]:
    if not files:
        return (False, "no change")
    if len(files) > max_files:
        return (False, f"touches {len(files)} files (> {max_files})")
    for f in files:
        low = f.lower()
        if "alembic/versions/" in low or "/migrations/" in low:
            return (False, f"touches a migration: {f}")
        if any(m in low for m in _FORBIDDEN_MARKERS):
            return (False, f"touches a forbidden path: {f}")
    return (True, "ok")


def gate_fix(cfg, worktree: Path, finding, changed: list[str], *, run_verify,
             skeptic) -> tuple[bool, str, int]:
    """Machine-verified gate for one applied refactor fix. Order: blast-radius → suite-green →
    adversarial self-check. Returns (passed, reason, skeptic_tokens) — the skeptic's token spend is
    surfaced so the caller counts it against the budget."""
    ok, why = blast_radius_ok(changed)
    if not ok:
        return (False, f"blast-radius: {why}", 0)
    passed, detail = run_verify(cfg, worktree)
    if not passed:
        tail = " ".join((detail or "").split())[:200]
        return (False, f"verify RED: {tail}", 0)
    verdict, reason, tokens = skeptic(finding, worktree)
    if verdict == "refuted":
        return (False, f"skeptic refuted: {reason}", tokens)
    return (True, "gate passed", tokens)
