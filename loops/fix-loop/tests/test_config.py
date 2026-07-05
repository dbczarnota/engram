from __future__ import annotations

from fix_config import load_fix_config


def test_load_reuses_reviewloop_yml(tmp_path):
    (tmp_path / ".reviewloop.yml").write_text(
        "verify:\n  test: uv run pytest -q\nreport_dir: reports\nbudget_tokens: 400000\n",
        encoding="utf-8")
    cfg = load_fix_config(tmp_path)
    assert cfg.verify.get("test") == "uv run pytest -q"
    assert cfg.budget_tokens == 400000
    assert cfg.per_fix_cap > 0 and cfg.max_files > 0


def test_fix_config_parses_setup(tmp_path):
    from fix_config import load_fix_config
    (tmp_path / ".reviewloop.yml").write_text(
        "setup:\n  deps: uv sync\nverify:\n  test: pytest\nreport_dir: reports\nbudget_tokens: 5\n",
        encoding="utf-8")
    cfg = load_fix_config(tmp_path)
    assert cfg.setup == {"deps": "uv sync"}


def test_fix_config_setup_defaults_empty(tmp_path):
    from fix_config import load_fix_config
    (tmp_path / ".reviewloop.yml").write_text("verify:\n  test: pytest\nreport_dir: reports\nbudget_tokens: 5\n", encoding="utf-8")
    assert load_fix_config(tmp_path).setup == {}


def test_fix_config_parses_coverage(tmp_path):
    from fix_config import load_fix_config
    (tmp_path / ".reviewloop.yml").write_text(
        'coverage: uv run pytest --cov=backend --cov-report=xml\nverify:\n  test: pytest\n'
        'report_dir: reports\nbudget_tokens: 5\n', encoding="utf-8")
    assert load_fix_config(tmp_path).coverage.startswith("uv run pytest --cov")
