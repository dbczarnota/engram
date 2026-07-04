import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crg_maintenance import sweep_db


def _make_db(path: Path, junk: int = 400, real: int = 6) -> None:
    c = sqlite3.connect(str(path))
    c.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, kind TEXT, qualified_name TEXT, file_path TEXT)")
    c.execute("CREATE TABLE edges (id INTEGER PRIMARY KEY, kind TEXT, source_qualified TEXT, "
              "target_qualified TEXT, file_path TEXT)")
    for i in range(junk):
        fp = rf"C:\r\frontend\node_modules\pkg\m{i}.js"
        c.execute("INSERT INTO nodes(kind,qualified_name,file_path) VALUES('Function',?,?)", (fp + "::f", fp))
        c.execute("INSERT INTO edges(kind,source_qualified,target_qualified,file_path) VALUES('CALLS',?,?,?)",
                  (fp + "::f", fp + "::g", fp))
    for i in range(real):
        fp = rf"C:\r\backend\svc{i}.py"
        c.execute("INSERT INTO nodes(kind,qualified_name,file_path) VALUES('Function',?,?)", (fp + "::f", fp))
    c.commit()
    c.close()


def test_sweep_prunes_junk_and_vacuums(tmp_path):
    db = tmp_path / "graph.db"
    _make_db(db)
    before, after, pruned = sweep_db(str(db))
    assert pruned == 400
    c = sqlite3.connect(str(db))
    assert c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 6           # only real remain
    assert c.execute("SELECT COUNT(*) FROM nodes WHERE file_path LIKE '%node_modules%'").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM edges").fetchone()[0] == 0           # junk edges gone
    c.close()
    assert after <= before                                                     # VACUUM reclaimed pages


def test_sweep_clean_db_is_noop_but_vacuums(tmp_path):
    db = tmp_path / "graph.db"
    _make_db(db, junk=0, real=5)
    before, after, pruned = sweep_db(str(db))
    assert pruned == 0                                                          # nothing to prune
    c = sqlite3.connect(str(db))
    assert c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 5
    c.close()
