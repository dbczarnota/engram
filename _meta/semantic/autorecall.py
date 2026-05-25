from __future__ import annotations

import json
import re
from pathlib import Path

import sqlite_vec

from index import connect, index_db_path
from query import rrf

_DEFAULT_AR = {
    "enabled": True,
    "topN": 3,
    "minScore": 0.30,
    "tokenBudget": 200,
    "scope": ["standards", "lessons", "decisions"],
}

_CUES = {
    "how",
    "why",
    "what",
    "should",
    "did",
    "do",
    "does",
    "when",
    "where",
    "which",
    "implement",
    "design",
    "build",
    "fix",
    "refactor",
    "architecture",
    "pattern",
    "standard",
    "decide",
    "approach",
    "jak",
    "czy",
    "dlaczego",
    "jakie",
    "gdzie",
    "kiedy",
    "zrób",
    "zaprojektuj",
}


# Words that are too common (or are our own substantive-gate cues) to count as evidence that a
# keyword-matched note is actually relevant. Used to reject single-coincidence FTS hits.
_STOP = _CUES | {
    "the",
    "a",
    "an",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "as",
    "at",
    "by",
    "our",
    "we",
    "you",
    "it",
    "this",
    "that",
    "these",
    "those",
    "us",
    "from",
    "into",
    "about",
    "please",
    "here",
    "there",
    "exactly",
    "clearly",
    "overall",
    "just",
    "really",
}


def _read_engram(vault_root: Path) -> dict:
    path = vault_root / "_meta" / "engram.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_config(vault_root: Path) -> dict:
    """autoRecall config merged over defaults; missing file/keys -> defaults."""
    return {**_DEFAULT_AR, **(_read_engram(vault_root).get("autoRecall") or {})}


def load_semantic_enabled(vault_root: Path) -> bool:
    """Whether the semantic (embedding) layer is enabled; gates auto-recall escalation + /recall tier."""
    return bool((_read_engram(vault_root).get("semantic") or {}).get("enabled", True))


def _meaningful_terms(prompt: str) -> list[str]:
    seen: list[str] = []
    for t in re.findall(r"\w+", prompt.lower()):
        if len(t) > 2 and t not in _STOP and t not in seen:
            seen.append(t)
    return seen


def is_substantive(prompt: str) -> bool:
    words = re.findall(r"\w+", prompt.lower())
    if len(words) >= 6 or "?" in prompt:
        return True
    return any(w in _CUES for w in words)


def _in_scope(path: str, scope: list[str]) -> bool:
    parts = set(Path(path).parts)
    return any(seg in parts for seg in scope)


def _row(con, cid: int):
    return con.execute("SELECT path, heading_path, text FROM chunks WHERE chunk_id=?", (cid,)).fetchone()


def _fts_candidates(con, prompt: str, scope: list[str], k: int = 20) -> list[tuple[int, tuple]]:
    # Match only on meaningful terms and require >=2 of them to actually appear in the note, so a
    # single coincidental keyword (often a common/cue word) does not surface a loosely-related note.
    meaningful = _meaningful_terms(prompt)
    if not meaningful:
        return []
    need = min(2, len(meaningful))
    rows = con.execute(
        "SELECT chunk_id FROM fts_chunks WHERE fts_chunks MATCH ? ORDER BY rank LIMIT ?",
        (" OR ".join(meaningful), k),
    ).fetchall()
    out: list[tuple[int, tuple]] = []
    for (cid,) in rows:
        r = _row(con, cid)
        if not r or not _in_scope(r[0], scope):
            continue
        text = f"{r[1]} {r[2]}".lower()  # heading + body
        if sum(1 for t in meaningful if t in text) >= need:
            out.append((cid, r))
    return out


def _vector_candidates(con, qvec, scope: list[str], min_score: float, k: int = 20):
    rows = con.execute(
        "SELECT chunk_id, distance FROM vec_chunks WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (sqlite_vec.serialize_float32(qvec), k),
    ).fetchall()
    out: list[tuple[int, tuple]] = []
    for cid, dist in rows:
        score = 1.0 - float(dist)
        if score < min_score:
            continue
        r = _row(con, cid)
        if r and _in_scope(r[0], scope):
            out.append((cid, r))
    return out


def _format(rows_in_order: list[tuple], token_budget: int) -> str | None:
    if not rows_in_order:
        return None
    header = "Engram auto-recall — possibly relevant notes:"
    lines = [header]
    char_budget = token_budget * 4  # ~4 chars/token proxy
    used = len(header)
    for path, heading, text in rows_in_order:
        snippet = " ".join(text.split())[:80]
        line = f"- {path} :: {heading} — {snippet}"
        if used + len(line) + 1 > char_budget and len(lines) > 1:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines) if len(lines) > 1 else None


def _seen_path(vault_root: Path, session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)
    return index_db_path(vault_root).parent / f"seen-{safe}.json"


def _load_seen(vault_root: Path, session_id: str | None) -> set[str]:
    if not session_id:
        return set()
    p = _seen_path(vault_root, session_id)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_seen(vault_root: Path, session_id: str | None, seen: set[str]) -> None:
    if not session_id:
        return
    try:
        _seen_path(vault_root, session_id).write_text(json.dumps(sorted(seen)), encoding="utf-8")
    except Exception:
        pass


def auto_recall(
    vault_root: Path,
    prompt: str,
    *,
    top_n: int,
    min_score: float,
    token_budget: int,
    scope: list[str],
    semantic_enabled: bool = True,
    session_id: str | None = None,
    embedder=None,
) -> str | None:
    """FTS-first proactive recall over scoped vault notes. Returns a hint or None.
    Best-effort: any failure returns None (never raises)."""
    try:
        if not is_substantive(prompt):
            return None
        db = index_db_path(vault_root)
        if not db.exists():
            return None
        con = connect(str(db))

        fts = _fts_candidates(con, prompt, scope, k=20)
        fts_ids = [cid for cid, _ in fts]
        strong_fts = fts_ids[:2]  # top-2 FTS = literal keyword confidence

        candidates: dict[int, tuple] = {cid: r for cid, r in fts if cid in strong_fts}

        vec_ids: list[int] = []
        if not strong_fts and semantic_enabled:  # escalate only when FTS is weak AND semantics are on
            from embedder import build_embedder

            emb = embedder or build_embedder()
            qvec = emb.embed_query(prompt)
            vec = _vector_candidates(con, qvec, scope, min_score, k=20)
            vec_ids = [cid for cid, _ in vec]
            for cid, r in vec:
                candidates.setdefault(cid, r)

        if not candidates:
            con.close()
            return None

        order = rrf([vec_ids, fts_ids], k=60)
        ordered_rows = [candidates[cid] for cid, _ in order if cid in candidates]
        for cid in candidates:  # include qualified candidates rrf didn't rank (e.g. strong FTS)
            if len(ordered_rows) >= top_n:
                break
            if candidates[cid] not in ordered_rows:
                ordered_rows.append(candidates[cid])
        con.close()

        seen = _load_seen(vault_root, session_id)
        fresh = [r for r in ordered_rows[:top_n] if r[0] not in seen]
        if not fresh:
            return None
        _save_seen(vault_root, session_id, seen | {r[0] for r in fresh})
        return _format(fresh, token_budget)
    except Exception:
        return None


def main() -> None:
    import sys

    vault_root = Path(__file__).resolve().parents[2]
    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    session_id = sys.argv[2] if len(sys.argv) > 2 else None
    cfg = load_config(vault_root)
    if not cfg.get("enabled", True):
        return
    hint = auto_recall(
        vault_root,
        prompt,
        top_n=int(cfg["topN"]),
        min_score=float(cfg["minScore"]),
        token_budget=int(cfg["tokenBudget"]),
        scope=list(cfg["scope"]),
        semantic_enabled=load_semantic_enabled(vault_root),
        session_id=session_id,
        embedder=None,
    )
    if hint:
        # Write raw UTF-8 bytes: the hint contains › and —, and the console codepage
        # (cp1252 on Windows) would otherwise mangle them. Avoids stdout.reconfigure quirks.
        sys.stdout.buffer.write((hint + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
