from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Callable

from config import ReviewLoopConfig


def parse_ruff(stdout: str) -> list[str]:
    data = json.loads(stdout)
    out: list[str] = []
    for d in data:
        loc = d.get("location") or {}
        out.append(f"{d.get('filename')}:{loc.get('row')} {d.get('code')} {d.get('message')}")
    return out


def parse_pyright(stdout: str) -> list[str]:
    data = json.loads(stdout)
    out: list[str] = []
    for d in data.get("generalDiagnostics") or []:
        severity = d.get("severity")
        if severity not in ("error", "warning"):
            continue  # skip "information"
        line = ((d.get("range") or {}).get("start") or {}).get("line", 0) + 1  # 0-based -> 1-based
        message = " ".join((d.get("message") or "").split())  # collapse pyright's multi-line detail tree
        out.append(f"{d.get('file')}:{line} {severity} [{d.get('rule')}] {message}")
    return out


def parse_eslint(stdout: str) -> list[str]:
    data = json.loads(stdout)
    sev = {2: "error", 1: "warning"}
    out: list[str] = []
    for f in data:
        for m in f.get("messages") or []:
            word = sev.get(m.get("severity"))
            if word is None:
                continue
            message = " ".join((m.get("message") or "").split())
            out.append(f"{f.get('filePath')}:{m.get('line')} {word} [{m.get('ruleId')}] {message}")
    return out


_TSC_LINE = re.compile(r"^(?P<file>.+?)\((?P<line>\d+),\d+\):\s+(?P<sev>error|warning)\s+(?P<code>TS\d+):\s+(?P<msg>.*)$")


def parse_tsc(stdout: str) -> list[str]:
    out: list[str] = []
    for raw in stdout.splitlines():
        m = _TSC_LINE.match(raw.strip())
        if not m:
            continue  # skip summary / blank / continuation lines
        out.append(f"{m['file']}:{m['line']} {m['sev']} [{m['code']}] {m['msg']}")
    return out


PARSERS: dict[str, Callable[[str], list[str]]] = {
    "ruff": parse_ruff,
    "pyright": parse_pyright,
    "eslint": parse_eslint,
    "tsc": parse_tsc,
}

_TIMEOUT_S = 300  # per-tool wall-clock cap; a hung tool becomes a tool_error, not a hang


def run_analysis(cfg: ReviewLoopConfig, path: Path) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    tool_errors: list[str] = []
    for tool, command in cfg.analysis.items():
        parser = PARSERS.get(tool)
        if parser is None:
            tool_errors.append(f"{tool}: no parser (supported: {', '.join(sorted(PARSERS))})")
            continue
        try:
            proc = subprocess.run(
                shlex.split(command), cwd=path,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=_TIMEOUT_S)
        except OSError as e:
            tool_errors.append(f"{tool}: could not run ({e})")
            continue
        except subprocess.TimeoutExpired:
            tool_errors.append(f"{tool}: timed out after {_TIMEOUT_S}s")
            continue
        try:
            findings.extend(parser(proc.stdout))  # nonzero exit is expected when issues exist
        except (json.JSONDecodeError, AttributeError, TypeError, KeyError):
            # valid-but-unexpected JSON shape must not crash the run
            tool_errors.append(f"{tool}: could not parse output (exit {proc.returncode})")
    return findings, tool_errors
