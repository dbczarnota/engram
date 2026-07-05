from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    qualified_name: str
    file: str            # repo-relative, forward-slashed
    line_start: int
    line_end: int
    lines: int
    degree: int
    signals: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class DesignProposal:
    philosophy: str      # e.g. "phase-pipeline"
    interface: str
    deep_modules: str
    weakness: str
    ok: bool = True      # False = agent failed/timed out/rate-limited


@dataclass
class RFC:
    candidate: Candidate
    recommendation: str
    markdown: str
