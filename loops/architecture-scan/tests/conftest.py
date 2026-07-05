import sqlite3
from pathlib import Path

import pytest


def _make_db(path: Path, nodes, edges):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, kind TEXT, name TEXT, "
                 "qualified_name TEXT, file_path TEXT, line_start INTEGER, line_end INTEGER, "
                 "is_test INTEGER)")
    conn.execute("CREATE TABLE edges (id INTEGER PRIMARY KEY, kind TEXT, "
                 "source_qualified TEXT, target_qualified TEXT)")
    conn.executemany("INSERT INTO nodes (kind,name,qualified_name,file_path,line_start,line_end,is_test)"
                     " VALUES (?,?,?,?,?,?,?)", nodes)
    conn.executemany("INSERT INTO edges (kind,source_qualified,target_qualified) VALUES (?,?,?)", edges)
    conn.commit()
    conn.close()


@pytest.fixture
def graph_db(tmp_path):
    """A repo at tmp_path with a graph.db. Returns (repo_root, db_path)."""
    repo = tmp_path
    dbdir = repo / ".code-review-graph"
    dbdir.mkdir()
    db = dbdir / "graph.db"
    root = str(repo).replace("/", "\\")
    def qn(rel, sym):
        return f"{root}\\{rel.replace('/', chr(92))}::{sym}"
    nodes = [
        # kind, name, qualified_name, file_path, line_start, line_end, is_test
        ("Function", "big_orch", qn("loops/x.py", "big_orch"), f"{root}\\loops\\x.py", 10, 150, 0),
        ("Function", "small", qn("loops/x.py", "small"), f"{root}\\loops\\x.py", 200, 210, 0),
        ("Function", "test_big", qn("loops/tests/test_x.py", "test_big"),
         f"{root}\\loops\\tests\\test_x.py", 1, 120, 1),
        ("Function", "stale", qn(".claude/worktrees/w/loops/x.py", "stale"),
         f"{root}\\.claude\\worktrees\\w\\loops\\x.py", 10, 200, 0),
        ("Function", "off_scope", qn("hooks/y.py", "off_scope"), f"{root}\\hooks\\y.py", 1, 90, 0),
    ]
    edges = [("CALLS", qn("loops/x.py", "big_orch"), qn("loops/x.py", "small")) for _ in range(20)]
    _make_db(db, nodes, edges)
    return repo, db
