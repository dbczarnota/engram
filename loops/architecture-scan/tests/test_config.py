from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scan_config import load_config


def test_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.report_dir == "loop-reports"
    assert cfg.top_k == 3
    assert cfg.max_rfcs == 3
    assert cfg.min_lines == 45
    assert cfg.paths == []


def test_yaml_overrides(tmp_path):
    (tmp_path / ".arch-scan.yml").write_text(
        "top_k: 1\nmin_lines: 60\npaths:\n  - loops/\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.top_k == 1
    assert cfg.min_lines == 60
    assert cfg.paths == ["loops/"]
    assert cfg.report_dir == "loop-reports"


def test_non_dict_yaml_falls_back_to_defaults(tmp_path):
    (tmp_path / ".arch-scan.yml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    cfg = load_config(tmp_path)   # must not raise
    assert cfg.top_k == 3 and cfg.report_dir == "loop-reports"
