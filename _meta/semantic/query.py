from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import sqlite_vec

from embedder import Embedder, build_embedder
from index import connect, index_db_path


class IndexMismatch(RuntimeError):
    """The configured embedder differs from the one the index was built with."""


@dataclass
class Hit:
    path: str
    heading_path: str
    snippet: str
    score: float


def rrf(ranked_lists: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion. rank is 1-based within each list."""
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, cid in enumerate(ranked, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def _fts_match(query: str) -> str:
    terms = re.findall(r"\w+", query.lower())
    return " OR ".join(terms)


def _check_identity(con: sqlite3.Connection, embedder: Embedder) -> None:
    row = con.execute("SELECT value FROM meta WHERE key='embedder'").fetchone()
    if row is None or row[0] != embedder.name:
        built = row[0] if row else "<none>"
        raise IndexMismatch(
            f"Index built with embedder {built!r} but configured embedder is {embedder.name!r}. Run reindex."
        )


def _vector_ids(con: sqlite3.Connection, qvec: list[float], k: int) -> list[int]:
    rows = con.execute(
        "SELECT chunk_id FROM vec_chunks WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (sqlite_vec.serialize_float32(qvec), k),
    ).fetchall()
    return [r[0] for r in rows]


def _fts_ids(con: sqlite3.Connection, query: str, k: int) -> list[int]:
    match = _fts_match(query)
    if not match:
        return []
    rows = con.execute(
        "SELECT chunk_id FROM fts_chunks WHERE fts_chunks MATCH ? ORDER BY rank LIMIT ?",
        (match, k),
    ).fetchall()
    return [r[0] for r in rows]


def search(
    vault_root: Path,
    query: str,
    *,
    embedder: Embedder | None = None,
    top_n: int = 8,
    k_each: int = 20,
    rrf_k: int = 60,
) -> list[Hit]:
    embedder = embedder or build_embedder()
    con = connect(str(index_db_path(vault_root)))
    _check_identity(con, embedder)
    qvec = embedder.embed_query(query)
    fused = rrf([_vector_ids(con, qvec, k_each), _fts_ids(con, query, k_each)], k=rrf_k)

    hits: list[Hit] = []
    for cid, score in fused[:top_n]:
        row = con.execute("SELECT path, heading_path, text FROM chunks WHERE chunk_id=?", (cid,)).fetchone()
        if row is None:
            continue
        path, heading_path, text = row
        snippet = " ".join(text.split())[:200]
        hits.append(Hit(path=path, heading_path=heading_path, snippet=snippet, score=score))
    con.close()
    return hits
