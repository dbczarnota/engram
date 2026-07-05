from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from config import ReviewLoopConfig

# Reuses command-center's proven Logfire query pattern (GET /v1/query?sql=, Authorization: <token>,
# columnar response) but with stdlib urllib — the review-loop is stdlib-only (+pyyaml).
LOGFIRE_BASE_DEFAULT = "https://logfire-eu.pydantic.dev"

# Recent exceptions / error-level records, project scoped by the read token (no project filter needed).
# A wrong default surfaces as a visible `errors` note (not a silent empty pass), so it can be tuned.
_DEFAULT_LOG_SQL = (
    "SELECT created_at, level, exception_type, message FROM records "
    "WHERE (is_exception OR level >= 17) "
    "AND created_at > now() - interval '24 hours' "
    "ORDER BY created_at DESC LIMIT 50"
)


def logfire_query(base: str, token: str, sql: str, *, timeout: float = 25.0) -> list[dict]:
    """GET the Logfire read/query API and transpose its columnar response to a list of row dicts."""
    url = f"{base}/v1/query?sql={urllib.parse.quote(sql)}"
    req = urllib.request.Request(url, headers={"Authorization": token})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    cols = payload.get("columns", [])
    if not cols:
        return []
    names = [c["name"] for c in cols]
    value_lists = [c["values"] for c in cols]
    return [dict(zip(names, row)) for row in zip(*value_lists)]


def _format(row: dict) -> str:
    ts = str(row.get("created_at") or "")
    kind = str(row.get("exception_type") or row.get("level") or "")
    msg = " ".join(str(row.get("message") or "").split())
    return f"{ts} {kind}: {msg}".strip()


def run_log_sweep(cfg: ReviewLoopConfig, *, query=logfire_query) -> tuple[list[str], list[str]]:
    """Query Logfire for recent errors. Returns (findings, errors). Never raises — every failure
    becomes an `errors` note so the run continues and the report stays honest."""
    if not cfg.logfire:
        return ([], [])
    token = os.environ.get("LOGFIRE_READ_TOKEN", "")
    if not token:
        return ([], ["log-sweep skipped: no LOGFIRE_READ_TOKEN"])
    base = os.environ.get("LOGFIRE_BASE", LOGFIRE_BASE_DEFAULT)
    try:
        rows = query(base, token, _DEFAULT_LOG_SQL)
        seen: set[str] = set()
        findings: list[str] = []
        for row in rows:
            line = _format(row)
            if line and line not in seen:
                seen.add(line)
                findings.append(line)
    except Exception as e:  # defensive I/O + parse boundary — never crash the run
        return ([], [f"log-sweep query error: {e}"])
    return (findings, [])
