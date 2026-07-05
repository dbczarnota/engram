from __future__ import annotations

from cli import parse_args


def test_parse_args_defaults():
    ns = parse_args(["/path/to/repo"])
    assert ns.repo == "/path/to/repo"
    assert ns.iter is None


def test_parse_args_iter_override():
    ns = parse_args(["/repo", "--iter", "3"])
    assert ns.iter == 3
