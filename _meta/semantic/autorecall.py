from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import sqlite_vec

from index import connect, index_db_path
from query import rrf

_DEFAULT_AR = {
    "enabled": True,
    "topN": 3,
    "minScore": 0.30,
    "tokenBudget": 350,
    "scope": ["standards", "lessons"],
    "includeProjectWiki": True,
    "tier2Min": 0.55,
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


def _note_in_scope(path: str, scope: list[str], include_project_wiki: bool) -> bool:
    parts = Path(path).parts
    if "_inbox" in parts:
        return False
    if any(seg in parts for seg in scope):
        return True
    # project wiki note: projects/<slug>/<slug>.md (filename stem == parent dir name)
    if include_project_wiki and len(parts) >= 3 and parts[0] == "projects":
        stem = Path(path).stem
        if stem == parts[-2] and stem not in ("journal", "todos"):
            return True
        if "features" in parts:  # feature notes (features/_inbox already excluded above)
            return True
    return False


def _row(con, cid: int):
    return con.execute("SELECT path, heading_path, text FROM chunks WHERE chunk_id=?", (cid,)).fetchone()


def _fts_candidates(con, prompt: str, scope: list[str], include_project_wiki: bool, k: int = 20) -> list[tuple[int, tuple]]:
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
        if not r or not _note_in_scope(r[0], scope, include_project_wiki):
            continue
        text = f"{r[1]} {r[2]}".lower()  # heading + body
        if sum(1 for t in meaningful if t in text) >= need:
            out.append((cid, r))
    return out


def _vector_candidates(con, qvec, scope: list[str], include_project_wiki: bool, min_score: float, k: int = 20):
    rows = con.execute(
        "SELECT chunk_id, distance FROM vec_chunks WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (sqlite_vec.serialize_float32(qvec), k),
    ).fetchall()
    out: list[tuple[int, tuple, float]] = []
    for cid, dist in rows:
        score = 1.0 - float(dist)
        if score < min_score:
            continue
        r = _row(con, cid)
        if r and _note_in_scope(r[0], scope, include_project_wiki):
            out.append((cid, r, score))
    return out


_SENT_RE = re.compile(r"(.+?[.!?])(\s|$)")


def _first_sentence(text: str) -> str:
    clean = " ".join(text.split())
    rule = re.search(r"\*\*Rule:\*\*\s*(.+?[.!?])", clean)
    if rule:
        return rule.group(1).strip()
    m = _SENT_RE.search(clean)
    return (m.group(1) if m else clean[:160]).strip()


def _format_tiered(rows, token_budget: int) -> str | None:
    """rows: list of (path, heading, text, score, tier). tier 2 => full chunk, tier 1 => pointer."""
    if not rows:
        return None
    header = "Engram auto-recall — possibly relevant notes:"
    lines = [header]
    char_budget = token_budget * 4
    used = len(header)
    for path, heading, text, _score, tier in rows:
        if tier >= 2:
            body = " ".join(text.split())[:500]
            line = f"- {path} :: {heading}\n  {body}"
        else:
            line = f"- {path} :: {heading} — {_first_sentence(text)}"
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


def _append_recall_log(vault_root: Path, *, prompt: str, paths: list[str], tier: int, score: float) -> None:
    try:
        d = vault_root / "_meta" / "state"
        d.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
            "paths": paths,
            "tier": tier,
            "score": round(float(score), 3),
        }
        with (d / "recall-log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
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
    include_project_wiki: bool = True,
    semantic_enabled: bool = True,
    session_id: str | None = None,
    embedder=None,
    tier2_min: float = 0.55,
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

        fts = _fts_candidates(con, prompt, scope, include_project_wiki, k=20)
        fts_ids = [cid for cid, _ in fts]
        strong_fts = fts_ids[:2]  # top-2 FTS = literal keyword confidence

        candidates: dict[int, tuple] = {cid: r for cid, r in fts if cid in strong_fts}

        score_by_cid: dict[int, float] = {}
        vec_ids: list[int] = []
        if not strong_fts and semantic_enabled:  # escalate only when FTS is weak AND semantics are on
            from embedder import build_embedder

            emb = embedder or build_embedder()
            qvec = emb.embed_query(prompt)
            vec = _vector_candidates(con, qvec, scope, include_project_wiki, min_score, k=20)
            vec_ids = [cid for cid, _, _s in vec]
            for cid, r, score in vec:
                score_by_cid[cid] = score
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

        # Build cid->row reverse map to look up tier per row
        cid_by_row: dict[int, int] = {id(r): cid for cid, r in candidates.items()}
        tiered_rows = []
        for r in fresh:
            cid = cid_by_row.get(id(r), -1)
            vec_score = score_by_cid.get(cid, 0.0)
            tier = 2 if (cid in strong_fts or vec_score >= tier2_min) else 1
            path, heading, text = r
            tiered_rows.append((path, heading, text, vec_score, tier))

        return _format_tiered(tiered_rows, token_budget)
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
        include_project_wiki=bool(cfg.get("includeProjectWiki", True)),
        tier2_min=float(cfg.get("tier2Min", 0.55)),
        semantic_enabled=load_semantic_enabled(vault_root),
        session_id=session_id,
        embedder=None,
    )
    if hint:
        # Write raw UTF-8 bytes: the hint contains › and —, and the console codepage
        # (cp1252 on Windows) would otherwise mangle them. Avoids stdout.reconfigure quirks.
        sys.stdout.buffer.write((hint + "\n").encode("utf-8"))
        # Parse surfaced paths from the hint for the recall log.
        # Lines look like: "- path/to/note.md :: Heading — snippet" (tier1) or
        #                   "- path/to/note.md :: Heading\n  body..." (tier2, no " — " after heading)
        surfaced_paths: list[str] = []
        hint_tier = 1
        for line in hint.splitlines():
            if line.startswith("- ") and " :: " in line:
                path_part = line[2:].split(" :: ")[0]
                surfaced_paths.append(path_part)
                # tier2 lines have no " — " separator after the heading
                if " — " not in line:
                    hint_tier = 2
        if surfaced_paths:
            _append_recall_log(vault_root, prompt=prompt, paths=surfaced_paths, tier=hint_tier, score=0.0)


if __name__ == "__main__":
    main()
