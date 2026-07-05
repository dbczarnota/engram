import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import run
from models import Candidate, DesignProposal, RFC
from publish import rfc_path


def test_end_to_end_files_and_reports(tmp_path):
    (tmp_path / ".code-review-graph").mkdir()
    (tmp_path / ".code-review-graph" / "graph.db").write_text("", encoding="utf-8")
    (tmp_path / ".arch-scan.yml").write_text("report_dir: loop-reports\n", encoding="utf-8")

    cand = Candidate("r::run", "loops/fix-loop/runner.py", 34, 168, 135, 172, ["large-function"], 651.0)

    def fake_discover(db, root, *, paths=(), min_lines=45, top_k=3):
        return [cand]

    def fake_design(candidate, root, **kw):
        return [DesignProposal("phase-pipeline", "i", "d", "w")]

    def fake_synth(candidate, proposals, root, **kw):
        return RFC(candidate=candidate, recommendation="rec", markdown="## Problem\nx")

    captured = {}

    def fake_publish(rfc, out_dir):
        captured["out_dir"] = str(out_dir)
        return ("filed", str(Path(out_dir) / "rfc.md"))

    report = run(tmp_path, "2026-07-04 1200", discover_fn=fake_discover, design_fn=fake_design,
                 synth_fn=fake_synth, publish_fn=fake_publish)
    text = report.read_text(encoding="utf-8")
    assert "r::run" in text
    assert "filed" in text
    assert "rec" in text
    assert captured["out_dir"].replace("\\", "/").endswith("loop-reports/architecture-scan")


def test_empty_discovery_writes_clean_report(tmp_path):
    (tmp_path / ".code-review-graph").mkdir()
    (tmp_path / ".code-review-graph" / "graph.db").write_text("", encoding="utf-8")
    report = run(tmp_path, "2026-07-04 1200",
                 discover_fn=lambda db, root, **kw: [],
                 design_fn=None, synth_fn=None, publish_fn=None)
    assert "0 candidate" in report.read_text(encoding="utf-8")


def test_rerun_skips_design_when_rfc_exists(tmp_path):
    (tmp_path / ".code-review-graph").mkdir()
    (tmp_path / ".code-review-graph" / "graph.db").write_text("", encoding="utf-8")
    (tmp_path / ".arch-scan.yml").write_text("report_dir: loop-reports\n", encoding="utf-8")
    cand = Candidate("r::run", "loops/fix-loop/runner.py", 34, 168, 135, 172, ["large-function"], 651.0)
    out_dir = tmp_path / "loop-reports" / "architecture-scan"
    out_dir.mkdir(parents=True)
    rfc_path(cand, out_dir).write_text("# existing", encoding="utf-8")   # pre-existing RFC

    def boom_design(*a, **k):
        raise AssertionError("design_fn must NOT be called when the RFC already exists")

    report = run(tmp_path, "2026-07-04 1200",
                 discover_fn=lambda db, root, **kw: [cand],
                 design_fn=boom_design, synth_fn=boom_design, publish_fn=boom_design)
    assert "duplicate" in report.read_text(encoding="utf-8")
