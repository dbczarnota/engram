from reindex import run


def test_run_returns_summary_string(tmp_path, fake_embedder):
    (tmp_path / "a.md").write_text("# A\n\nhello world\n", encoding="utf-8")
    summary = run(tmp_path, embedder=fake_embedder)
    assert "files=1" in summary
    assert "chunks=" in summary
    assert (tmp_path / "_meta" / "semantic" / ".index" / "index.db").exists()


def test_reindex_prunes_seen_files(tmp_path, fake_embedder):
    (tmp_path / "a.md").write_text("# A\n\nhello world\n", encoding="utf-8")
    run(tmp_path, embedder=fake_embedder)
    seen = tmp_path / "_meta" / "semantic" / ".index" / "seen-abc.json"
    seen.write_text("[]", encoding="utf-8")
    run(tmp_path, embedder=fake_embedder)
    assert not seen.exists()
