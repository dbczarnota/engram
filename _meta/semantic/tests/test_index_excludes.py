# _meta/semantic/tests/test_index_excludes.py
from pathlib import Path

from index import _iter_markdown


def test_inbox_and_archive_excluded(tmp_path: Path):
    (tmp_path / "lessons" / "_inbox").mkdir(parents=True)
    (tmp_path / "lessons" / "_inbox" / "draft.md").write_text("x", encoding="utf-8")
    (tmp_path / "lessons" / "real.md").write_text("y", encoding="utf-8")
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "old.md").write_text("z", encoding="utf-8")

    found = {p.relative_to(tmp_path).as_posix() for p in _iter_markdown(tmp_path)}
    assert "lessons/real.md" in found
    assert "lessons/_inbox/draft.md" not in found
    assert "archive/old.md" not in found
