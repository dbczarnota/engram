from pathlib import Path

from index import build_index, connect, index_db_path


def _write_vault(root: Path) -> None:
    (root / "standards").mkdir(parents=True)
    (root / "standards" / "auth.md").write_text(
        "# Auth\n\nWe use X-API-Key for clients and Kinde JWT for dashboards.\n",
        encoding="utf-8",
    )
    (root / "lessons").mkdir()
    (root / "lessons" / "py.md").write_text("# Python\n\nruff and pyright notes.\n", encoding="utf-8")
    (root / "archive").mkdir()
    (root / "archive" / "old.md").write_text("# Old\n\nshould not be indexed\n", encoding="utf-8")
    venv = root / "_meta" / "semantic" / ".venv"
    venv.mkdir(parents=True)
    (venv / "README.md").write_text("# Dep readme\n\npackage docs, not a note\n", encoding="utf-8")


def test_build_index_indexes_chunks_excluding_archive(tmp_path, fake_embedder):
    _write_vault(tmp_path)
    stats = build_index(tmp_path, fake_embedder)
    assert stats.files == 2  # archive excluded
    assert stats.chunks >= 2

    con = connect(str(index_db_path(tmp_path)))
    paths = {row[0] for row in con.execute("SELECT DISTINCT path FROM chunks")}
    assert "standards/auth.md" in paths
    assert "archive/old.md" not in paths
    assert not any(".venv" in p for p in paths)
    (n_vec,) = con.execute("SELECT count(*) FROM vec_chunks").fetchone()
    (n_fts,) = con.execute("SELECT count(*) FROM fts_chunks").fetchone()
    (n_chunks,) = con.execute("SELECT count(*) FROM chunks").fetchone()
    assert n_vec == n_fts == n_chunks


def test_meta_records_embedder_identity(tmp_path, fake_embedder):
    _write_vault(tmp_path)
    build_index(tmp_path, fake_embedder)
    con = connect(str(index_db_path(tmp_path)))
    (val,) = con.execute("SELECT value FROM meta WHERE key='embedder'").fetchone()
    assert val == fake_embedder.name


def test_second_build_reuses_cache(tmp_path, fake_embedder):
    _write_vault(tmp_path)
    build_index(tmp_path, fake_embedder)
    stats2 = build_index(tmp_path, fake_embedder)
    assert stats2.embedded == 0  # all served from cache
    assert stats2.cached == stats2.chunks
