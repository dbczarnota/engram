import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from publish import publish
from models import Candidate, RFC


def _rfc():
    c = Candidate("r::run", "loops/fix-loop/runner.py", 34, 168, 135, 172, ["large-function"], 651.0)
    return RFC(candidate=c, recommendation="strategy-outcome", markdown="## Problem\nbody")


def test_filed_writes_rfc_file(tmp_path):
    out, detail = publish(_rfc(), tmp_path / "architecture-scan")
    assert out == "filed"
    p = Path(detail)
    assert p.exists() and p.parent == tmp_path / "architecture-scan"
    text = p.read_text(encoding="utf-8")
    assert "strategy-outcome" in text          # recommendation in header
    assert "## Problem" in text                 # rfc markdown body


def test_dedup_second_run_is_duplicate(tmp_path):
    out_dir = tmp_path / "architecture-scan"
    publish(_rfc(), out_dir)
    before = sorted(p.name for p in out_dir.iterdir())
    out, detail = publish(_rfc(), out_dir)
    assert out == "duplicate"
    assert sorted(p.name for p in out_dir.iterdir()) == before    # no new file
