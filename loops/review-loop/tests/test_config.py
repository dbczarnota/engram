from __future__ import annotations

import pytest

from config import ConfigError, ReviewLoopConfig, load_config
from tests.conftest import VALID_YML


def test_load_valid_config(repo_with_config):
    _, write = repo_with_config
    root = write(VALID_YML)
    cfg = load_config(root)
    assert cfg.verify["test"] == "pytest -q"
    assert cfg.backend == ["app/**"]
    assert cfg.logfire == "myrepo"
    assert cfg.db is True
    assert cfg.max_iter == 2
    assert cfg.budget_tokens == 400000


def test_missing_config_raises(tmp_path):
    with pytest.raises(ConfigError, match="no .reviewloop.yml"):
        load_config(tmp_path)


def test_missing_report_dir_raises(repo_with_config):
    _, write = repo_with_config
    root = write("verify: {}\nmax_iter: 2\nbudget_tokens: 1000\n")
    with pytest.raises(ConfigError, match="report_dir"):
        load_config(root)


def test_optional_capabilities_default(repo_with_config):
    _, write = repo_with_config
    root = write('max_iter: 1\nbudget_tokens: 500\nreport_dir: "r"\nverify: {}\n')
    cfg = load_config(root)
    assert cfg.logfire is None
    assert cfg.db is False
    assert cfg.frontend == []


def test_analysis_block_parsed(repo_with_config):
    _, write = repo_with_config
    root = write(
        'verify: {}\nmax_iter: 1\nbudget_tokens: 500\nreport_dir: "r"\n'
        'analysis:\n  ruff: "ruff check . --output-format json"\n  pyright: "pyright --outputjson"\n'
    )
    cfg = load_config(root)
    assert cfg.analysis == {
        "ruff": "ruff check . --output-format json",
        "pyright": "pyright --outputjson",
    }


def test_analysis_defaults_empty(repo_with_config):
    _, write = repo_with_config
    root = write('verify: {}\nmax_iter: 1\nbudget_tokens: 500\nreport_dir: "r"\n')
    assert load_config(root).analysis == {}


def test_config_fanout_defaults_false_and_parses_true(repo_with_config):
    _, write = repo_with_config
    base = ("verify: {}\nreport_dir: r\nmax_iter: 1\nbudget_tokens: 1\n")
    root = write(base)
    assert load_config(root).fanout is False
    root = write(base + "fanout: true\n")
    assert load_config(root).fanout is True
