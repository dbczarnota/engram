from __future__ import annotations

import re
from dataclasses import dataclass, field

from baseline import CommandResult

_ENV_EXIT = {124, 126, 127}
_ENV_MARKERS = (
    "collected 0 items", "no tests ran", "errors during collection", "modulenotfounderror",
    "importerror", "connection refused", "could not connect", "docker", "testcontainers",
    "cannot connect to the docker daemon",
)
_PYTEST_FAILED = re.compile(r"^FAILED\s+(\S+)", re.MULTILINE)
# pytest short-summary ERROR lines (fixture/collection errors) — tracked separately from FAILED: an ERROR
# is not a repair TARGET (it is usually env/fixture), but a NEW error introduced by a fix is still a
# regression the monotonic gate must reject.
_PYTEST_ERROR = re.compile(r"^ERROR\s+(\S+)", re.MULTILINE)
# ruff/flake8/mypy: `path:line:col: msg`  |  pyright: `  <path>:line:col - error: msg` (INDENTED, and
# on Windows the path is an absolute drive path like `c:\...\file.py`). Allow leading whitespace and a
# drive-letter colon by matching up to the first `.py` (non-greedy), then `:line:col`.
_LINE_TOOL = re.compile(r"^\s*(?P<file>.+?\.py):(?P<line>\d+):(?P<col>\d+)(?::|\s-\s)", re.MULTILINE)


@dataclass
class Failure:
    id: str
    command: str
    file: str
    snippet: str


@dataclass
class TriageResult:
    blocked_env: list[str] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    # names of verify commands that FAILED but produced no harvestable failure — i.e. could not run
    # to a targetable result (environment/infra, collection break, or unparseable output). Tracked so the
    # repair gate can reject a "fix" that turns a previously-runnable command un-runnable (e.g. a syntax
    # error that breaks pytest collection — which otherwise looks like "no failures = green").
    env_commands: set[str] = field(default_factory=set)
    # pytest nodeids reported as ERROR (fixture/collection) — not repair targets, but the gate treats a
    # NEW error as a regression (folded into the baseline comparison set).
    errors: set[str] = field(default_factory=set)


def _is_env(res: CommandResult) -> bool:
    if res.exit_code in _ENV_EXIT:
        return True
    low = res.output.lower()
    return any(m in low for m in _ENV_MARKERS)


def _harvest(res: CommandResult) -> list[Failure]:
    out: list[Failure] = []
    for nodeid in _PYTEST_FAILED.findall(res.output):
        out.append(Failure(id=nodeid, command=res.command,
                           file=nodeid.split("::", 1)[0], snippet=nodeid))
    for m in _LINE_TOOL.finditer(res.output):
        fid = f"{m.group('file')}:{m.group('line')}:{m.group('col')}"
        line = res.output[m.start():].splitlines()[0].strip()
        out.append(Failure(id=fid, command=res.command, file=m.group("file"), snippet=line))
    return out


def classify(results: list[CommandResult]) -> TriageResult:
    tr = TriageResult()
    for res in results:
        if res.exit_code == 0:
            continue
        # Harvest genuine failures FIRST: a run with real FAILED/tool lines is a genuine-bug run even if
        # its output happens to mention "docker"/"ImportError" in a traceback — do not let an env marker
        # mask real failures.
        tr.errors.update(_PYTEST_ERROR.findall(res.output))
        harvested = _harvest(res)
        if harvested:
            tr.failures.extend(harvested)
            continue
        # A failed command with nothing harvestable could not produce a targetable result: environment /
        # collection break / unparseable. Record the command as un-runnable (env_commands) either way.
        tr.env_commands.add(res.name)
        if _is_env(res):
            tail = " ".join(res.output.split())[:160]
            tr.blocked_env.append(f"[{res.name}] environment/infra (exit {res.exit_code}): {tail}")
        else:
            tr.blocked_env.append(f"[{res.name}] unparseable failure (exit {res.exit_code})")
    return tr


def is_pre_flight_blocked(tr: TriageResult) -> bool:
    """The suite could not really run: there are environment blocks and NOT ONE genuine failure."""
    return bool(tr.blocked_env) and not tr.failures
