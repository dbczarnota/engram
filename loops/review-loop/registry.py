from __future__ import annotations

import os
import subprocess
from pathlib import Path

from report import Finding

_COLUMNS = ["fingerprint", "file", "dimension", "severity", "fix_class", "summary",
            "status", "branch", "cost", "attempts", "first_seen", "last_seen", "misses"]

# dimension -> fix_class. refactor = behavior-preserving (suite-green gate); bug = behavior-changing.
_BUG_DIMENSIONS = {"bug-hunt", "security", "consistency"}


def _fix_class(dimension: str) -> str:
    return "bug" if dimension in _BUG_DIMENSIONS else "refactor"


def _esc(value: str) -> str:
    # markdown table cells: no raw pipes/newlines
    return " ".join(str(value).replace("|", "\\|").split())


def render_registry(rows: list[dict]) -> str:
    head = ("---\ntype: bug-registry\nowner: review-loop+fix-loop\n"
            "note: machine-owned; do not hand-edit except status->wontfix\n---\n\n"
            "# Bug registry\n\n")
    header = "| " + " | ".join(_COLUMNS) + " |\n"
    sep = "| " + " | ".join("---" for _ in _COLUMNS) + " |\n"
    body = "".join("| " + " | ".join(_esc(r.get(c, "")) for c in _COLUMNS) + " |\n" for r in rows)
    return head + header + sep + body


def parse_registry(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells == _COLUMNS or cells == _COLUMNS[:-1] or all(set(c) <= {"-"} for c in cells):
            continue  # header (new or old) or separator
        # Handle escaped pipes: merge cells that end with backslash with the next cell
        merged: list[str] = []
        i = 0
        while i < len(cells):
            cell = cells[i]
            while i < len(cells) - 1 and cell.endswith("\\"):
                # The backslash is escaping the next pipe, so merge
                cell = cell[:-1] + "|" + cells[i + 1]
                i += 1
            merged.append(cell)
            i += 1
        if len(merged) == len(_COLUMNS) - 1:
            merged.append("0")          # old registry: backfill misses -> 0
        if len(merged) != len(_COLUMNS):
            continue
        # Unescape remaining escaped pipes
        merged = [c.replace("\\|", "|") for c in merged]
        rows.append(dict(zip(_COLUMNS, merged)))
    return rows


def _merged_branches(repo: Path) -> set[str]:
    """Branches already merged into master. Best-effort: any git failure -> empty set (treat nothing as
    merged, so fixes stay 'fixed' rather than being falsely flagged regressed)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "branch", "--merged", "master", "--format=%(refname:short)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if out.returncode != 0:
            return set()
        return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}
    except (OSError, subprocess.TimeoutExpired):
        return set()


def update_registry(existing_rows: list[dict], findings: list[Finding], today: str,
                    *, is_merged=lambda branch: False, resolve_after: int = 2,
                    scan_complete: bool = True) -> list[dict]:
    """Dedup findings into the registry by fingerprint + reconcile lifecycle. A finding lives on an
    unmerged `fix/*` branch off master, so re-detecting a fixed+UNMERGED finding keeps it `fixed`; only a
    MERGED fix still detected becomes `regressed`. Absence is the ground-truth "resolved" signal: a row
    not detected for `resolve_after` consecutive runs settles to `resolved` (reversible — a returning
    finding reopens). `wontfix` is manual and never auto-touched. `failed` re-queues on re-detection."""
    seen = {f.fingerprint for f in findings}
    by_fp = {r["fingerprint"]: dict(r) for r in existing_rows}
    for f in findings:
        if f.fingerprint not in by_fp:
            by_fp[f.fingerprint] = {
                "fingerprint": f.fingerprint, "file": f.file, "dimension": f.dimension,
                "severity": f.severity, "fix_class": _fix_class(f.dimension), "summary": f.summary,
                "status": "pending", "branch": "", "cost": "", "attempts": "0",
                "first_seen": today, "last_seen": today, "misses": "0"}
    for fp, cur in by_fp.items():
        if fp in seen:
            cur["last_seen"] = today
            cur["misses"] = "0"
            st = cur.get("status")
            if st == "resolved":
                cur["status"] = "pending"                     # reopened — the finding came back
            elif st == "failed":
                cur["status"] = "pending"                     # re-queue; _fail caps at attempts>=3
            elif st == "fixed" and cur.get("branch") and is_merged(cur["branch"]):
                cur["status"] = "regressed"                   # merged fix, bug is back
            # fixed+unmerged / pending / needs-human / in-progress / wontfix / subsumed / deferred: keep
        elif scan_complete:
            # Absence is only a trustworthy signal when the scan actually completed — a failed/partial
            # scan (rate-limited, api-error, no-output) yields empty findings for reasons that have
            # nothing to do with the bug being gone, so it must never count as a "miss".
            if cur.get("status") in ("resolved", "wontfix"):
                continue                                       # terminal — leave as-is
            cur["misses"] = str(int(cur.get("misses") or 0) + 1)
            if int(cur["misses"]) >= resolve_after:
                cur["status"] = "resolved"
    return list(by_fp.values())


def write_registry(path: Path, findings: list[Finding], today: str, *,
                   scan_complete: bool = True) -> list[dict]:
    """Merge findings into the registry markdown and write atomically. Never raises. Returns the
    reconciled rows (or [] on failure) so the caller can render them into the report. The registry sits at
    the target repo root, so its parent is that git repo — used to tell merged fixes from regressions."""
    try:
        existing = parse_registry(path.read_text(encoding="utf-8")) if path.is_file() else []
        merged = _merged_branches(path.parent)
        rows = update_registry(existing, findings, today, is_merged=lambda b: b in merged,
                               scan_complete=scan_complete)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(render_registry(rows), encoding="utf-8")
        os.replace(tmp, path)
        return rows
    except Exception:
        return []  # defensive: registry write must never break a review run
