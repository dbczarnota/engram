from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_NAME = ".reviewloop.yml"


class ConfigError(RuntimeError):
    """The repo's .reviewloop.yml is missing or invalid."""


@dataclass
class ReviewLoopConfig:
    verify: dict[str, str]
    report_dir: str
    max_iter: int
    budget_tokens: int
    backend: list[str] = field(default_factory=list)
    frontend: list[str] = field(default_factory=list)
    logfire: str | None = None
    db: bool = False
    analysis: dict[str, str] = field(default_factory=dict)
    fanout: bool = False


def load_config(repo_root: Path) -> ReviewLoopConfig:
    path = repo_root / CONFIG_NAME
    if not path.is_file():
        raise ConfigError(f"no {CONFIG_NAME} in {repo_root}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for required in ("report_dir", "max_iter", "budget_tokens"):
        if required not in data:
            raise ConfigError(f"{CONFIG_NAME} missing required key: {required}")
    caps = data.get("capabilities") or {}
    return ReviewLoopConfig(
        verify=data.get("verify") or {},
        report_dir=str(data["report_dir"]),
        max_iter=int(data["max_iter"]),
        budget_tokens=int(data["budget_tokens"]),
        backend=list(data.get("backend") or []),
        frontend=list(data.get("frontend") or []),
        logfire=caps.get("logfire"),
        db=bool(caps.get("db", False)),
        analysis=dict(data.get("analysis") or {}),
        fanout=bool(data.get("fanout", False)),
    )
