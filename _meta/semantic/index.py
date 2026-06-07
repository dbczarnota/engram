from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import sqlite_vec

from chunking import Chunk, chunk_markdown, embed_input
from embedder import Embedder

_INDEX_DIR = ("_meta", "semantic", ".index")
_SEMANTIC_DIR = ("_meta", "semantic")  # the tool's own code + venv — never knowledge notes


def ensure_vec_loadable() -> None:
    """Raise a clear error if sqlite-vec's loadable extension is unavailable.

    This is the Windows de-risking gate (spec §7). enable_load_extension may be
    compiled out of some Python builds; sqlite_vec.load may fail to find the binary.
    """
    con = sqlite3.connect(":memory:")
    try:
        con.enable_load_extension(True)
    except AttributeError as exc:  # extension loading compiled out
        raise RuntimeError(
            "This Python's sqlite3 has extension loading disabled — sqlite-vec cannot load. "
            "Fall back to the numpy path (spec §7)."
        ) from exc
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    con.execute("CREATE VIRTUAL TABLE t USING vec0(embedding FLOAT[3])")
    con.close()


def connect(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with sqlite-vec loaded."""
    con = sqlite3.connect(db_path)
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    return con


def index_dir(vault_root: Path) -> Path:
    return vault_root.joinpath(*_INDEX_DIR)


def index_db_path(vault_root: Path) -> Path:
    return index_dir(vault_root) / "index.db"


def cache_db_path(vault_root: Path) -> Path:
    return index_dir(vault_root) / "cache.db"


@dataclass
class IndexStats:
    files: int
    chunks: int
    embedded: int  # newly embedded this run
    cached: int  # served from cache


def _iter_markdown(vault_root: Path) -> list[Path]:
    out: list[Path] = []
    for p in vault_root.rglob("*.md"):
        rel = p.relative_to(vault_root)
        parts = rel.parts
        if parts[0] == "archive" or ".git" in parts:
            continue
        if "_inbox" in parts:  # staged lesson drafts — never indexed until promoted
            continue
        if parts[:2] == _SEMANTIC_DIR:  # excludes the tool dir, its .venv and .index
            continue
        out.append(p)
    return out


def _open_cache(vault_root: Path) -> sqlite3.Connection:
    cache = connect(str(cache_db_path(vault_root)))
    cache.execute(
        "CREATE TABLE IF NOT EXISTS cache("
        "content_hash TEXT NOT NULL, embedder TEXT NOT NULL, dim INTEGER NOT NULL, "
        "vector BLOB NOT NULL, PRIMARY KEY (content_hash, embedder))"
    )
    return cache


def _embed_with_cache(
    chunks: list[Chunk], embedder: Embedder, cache: sqlite3.Connection
) -> tuple[list[bytes], int, int]:
    """Return one serialized vector per chunk, reusing cache by (content_hash, embedder)."""
    vectors: list[bytes | None] = [None] * len(chunks)
    misses: list[int] = []
    for i, c in enumerate(chunks):
        row = cache.execute(
            "SELECT vector FROM cache WHERE content_hash=? AND embedder=?",
            (c.content_hash, embedder.name),
        ).fetchone()
        if row is None:
            misses.append(i)
        else:
            vectors[i] = row[0]

    if misses:
        new = embedder.embed_documents([embed_input(chunks[i]) for i in misses])
        for i, vec in zip(misses, new):
            blob = sqlite_vec.serialize_float32(vec)
            vectors[i] = blob
            cache.execute(
                "INSERT OR REPLACE INTO cache(content_hash, embedder, dim, vector) VALUES (?,?,?,?)",
                (chunks[i].content_hash, embedder.name, embedder.dim, blob),
            )
        cache.commit()

    return [v for v in vectors if v is not None], len(misses), len(chunks) - len(misses)


def build_index(vault_root: Path, embedder: Embedder) -> IndexStats:
    """Full rebuild of index.db; embeddings reused from cache.db where unchanged."""
    ensure_vec_loadable()
    index_dir(vault_root).mkdir(parents=True, exist_ok=True)

    files = _iter_markdown(vault_root)
    chunks: list[Chunk] = []
    for p in files:
        rel = p.relative_to(vault_root).as_posix()
        chunks.extend(chunk_markdown(rel, p.read_text(encoding="utf-8")))

    cache = _open_cache(vault_root)
    vectors, embedded, cached = _embed_with_cache(chunks, embedder, cache)
    cache.close()

    db = index_db_path(vault_root)
    if db.exists():
        db.unlink()
    con = connect(str(db))
    con.execute(
        "CREATE TABLE chunks(chunk_id INTEGER PRIMARY KEY, path TEXT NOT NULL, "
        "heading_path TEXT NOT NULL, text TEXT NOT NULL, content_hash TEXT NOT NULL)"
    )
    con.execute(
        "CREATE VIRTUAL TABLE vec_chunks USING vec0("
        f"chunk_id INTEGER PRIMARY KEY, embedding FLOAT[{embedder.dim}] distance_metric=cosine)"
    )
    con.execute("CREATE VIRTUAL TABLE fts_chunks USING fts5(chunk_id UNINDEXED, text)")
    con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")

    for i, c in enumerate(chunks, start=1):
        con.execute(
            "INSERT INTO chunks(chunk_id, path, heading_path, text, content_hash) VALUES (?,?,?,?,?)",
            (i, c.path, c.heading_path, c.text, c.content_hash),
        )
        con.execute("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", (i, vectors[i - 1]))
        con.execute("INSERT INTO fts_chunks(chunk_id, text) VALUES (?, ?)", (i, embed_input(c)))

    con.execute("INSERT INTO meta(key, value) VALUES ('embedder', ?)", (embedder.name,))
    con.execute("INSERT INTO meta(key, value) VALUES ('dim', ?)", (str(embedder.dim),))
    con.commit()
    con.close()
    return IndexStats(files=len(files), chunks=len(chunks), embedded=embedded, cached=cached)
