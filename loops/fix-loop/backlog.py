from __future__ import annotations

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "": 4}
# lower rank = higher priority
_DIMENSION_RANK = {"security": 0, "bug-hunt": 1, "consistency": 2, "perf": 3,
                   "dead-code": 4, "dedup": 5, "complexity": 6, "static-analysis": 7}
_OPEN = {"pending", "regressed"}


def _priority(row: dict) -> tuple[int, int]:
    return (_SEVERITY_RANK.get(row.get("severity", ""), 4),
            _DIMENSION_RANK.get(row.get("dimension", ""), 9))


def select_fixes(rows: list[dict], *, fix_classes=("refactor",), max_attempts: int = 3) -> list[dict]:
    """Open (pending/regressed) findings of the given fix_classes, under the attempt cap, ordered by
    priority (severity, then dimension)."""
    def _attempts(r: dict) -> int:
        try:
            return int(r.get("attempts") or 0)
        except ValueError:
            return 0
    picked = [r for r in rows
              if r.get("status") in _OPEN
              and r.get("fix_class") in fix_classes
              and _attempts(r) < max_attempts]
    return sorted(picked, key=_priority)


def dedup_key(row: dict) -> tuple[str, str, str] | None:
    """Coarse region key (file, symbol, dimension) used to skip redundant fixes: two findings on the same
    function+dimension (e.g. two N+1s in one function) get fixed together by the first fix, so the rest
    are `subsumed` and never produce a second overlapping branch. Returns None for findings without a
    parseable `file.py:symbol:slug` fingerprint (e.g. static-analysis) — those are line-specific, never
    deduped."""
    fp = row.get("fingerprint", "")
    parts = fp.rsplit(":", 2)
    if len(parts) != 3:
        return None
    file_, symbol, _slug = parts
    if not symbol or not file_.endswith(".py"):
        return None
    return (file_, symbol, row.get("dimension", ""))


def set_status(rows: list[dict], fingerprint: str, status: str, **fields) -> list[dict]:
    """Return rows with the matching fingerprint's status (+ any extra fields) updated."""
    out = []
    for r in rows:
        if r.get("fingerprint") == fingerprint:
            r = {**r, "status": status, **{k: str(v) for k, v in fields.items()}}
        out.append(r)
    return out
