import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discover import discover_candidates, _in_scope, _is_noise


def test_picks_large_in_scope_function(graph_db):
    repo, db = graph_db
    cands = discover_candidates(db, repo, paths=["loops/"], min_lines=45, top_k=3)
    names = [c.qualified_name.split("::")[-1] for c in cands]
    assert "big_orch" in names            # 141 lines, in scope
    assert "small" not in names           # 11 lines < min
    assert "test_big" not in names        # test file
    assert "stale" not in names           # .claude/worktrees
    assert "off_scope" not in names       # not under paths=[loops/]


def test_relative_file_and_degree(graph_db):
    repo, db = graph_db
    cand = discover_candidates(db, repo, paths=["loops/"], min_lines=45, top_k=1)[0]
    assert cand.file == "loops/x.py"      # repo-relative, forward-slashed
    assert cand.degree == 20              # 20 CALLS out-edges
    assert "large-function" in cand.signals
    assert cand.score == 141 + 3 * 20     # lines + 3*degree


def test_scope_has_directory_boundary():
    root = Path("C:/repo")
    assert _in_scope("C:/repo/loops/x.py", root, ["loops"]) is True
    assert _in_scope("C:/repo/loops-old/x.py", root, ["loops"]) is False
    assert _in_scope("C:/repo/loops/x.py", root, ["loops/"]) is True


def test_noise_filter_excludes_deps_venvs_and_worktrees():
    # CRG can index these when its graph is dirty (Windows update re-adds them); discovery must
    # exclude them defensively so they never surface as refactor candidates.
    for junk in (
        r"C:\repo\.venv\Lib\site-packages\pkg\mod.py",
        r"C:\repo\.worktrees\feat-x\backend\services\thing.py",   # HF-style worktree
        r"C:\repo\.claude\worktrees\w\loops\x.py",                # brain-style worktree
        r"C:\repo\frontend\node_modules\pkg\index.js",
        r"C:\repo\backend\.venv\Scripts\activate_this.py",
    ):
        assert _is_noise(junk) is True, junk
    # real app code is NOT noise
    for real in (
        r"C:\repo\backend\services\discovery\poller.py",
        r"C:\repo\loops\fix-loop\runner.py",
    ):
        assert _is_noise(real) is False, real
