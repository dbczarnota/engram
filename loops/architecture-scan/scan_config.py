from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_NAME = ".arch-scan.yml"


@dataclass
class ArchScanConfig:
    report_dir: str = "loop-reports"
    top_k: int = 3
    max_rfcs: int = 3
    min_lines: int = 45
    paths: list[str] = field(default_factory=list)


def load_config(repo_root: Path) -> ArchScanConfig:
    path = repo_root / CONFIG_NAME
    data = {}
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            data = {}
    cfg = ArchScanConfig()
    return ArchScanConfig(
        report_dir=str(data.get("report_dir", cfg.report_dir)),
        top_k=int(data.get("top_k", cfg.top_k)),
        max_rfcs=int(data.get("max_rfcs", cfg.max_rfcs)),
        min_lines=int(data.get("min_lines", cfg.min_lines)),
        paths=list(data.get("paths") or []),
    )
