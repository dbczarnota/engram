from __future__ import annotations

from dataclasses import dataclass

_MECHANICAL = {"dedup", "dead-code", "static-analysis"}
_LOGIC = {"perf", "complexity", "consistency"}
_SENSITIVE_DIM = {"security", "bug-hunt"}
_SENSITIVE_MARKERS = ("alembic/versions", "migrations", "k8s", "deploy", ".github", "dockerfile",
                      "auth", "security", "tenant", "rbac", "permission", "secret")

TIER_RANK = {"needs-human": 0, "canary": 1, "prod-safe": 2}


def _is_sensitive_path(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    segs = p.split("/")
    for m in _SENSITIVE_MARKERS:
        if "/" in m:
            if m in p:
                return True
        elif any(m in seg for seg in segs):   # word appears in any path segment (incl. root basename)
            return True
    return False


def _dimension_class(dimension: str) -> str:
    if dimension in _MECHANICAL:
        return "mechanical"
    if dimension in _SENSITIVE_DIM:
        return "sensitive"
    return "logic"


@dataclass
class Signals:
    dimension_class: str
    files_changed: int
    lines_changed: int
    small: bool
    sensitive: bool


def compute_signals(dimension: str, changed_files: list[str], lines_changed: int, *,
                    max_files: int = 5, max_lines: int = 40) -> Signals:
    dclass = _dimension_class(dimension)
    sensitive_path = any(_is_sensitive_path(f) for f in changed_files)
    sensitive = dclass == "sensitive" or sensitive_path
    small = len(changed_files) <= max_files and lines_changed <= max_lines
    return Signals(dimension_class=dclass, files_changed=len(changed_files),
                   lines_changed=lines_changed, small=small, sensitive=sensitive)


def floor_tier(sig: Signals) -> str:
    if sig.sensitive:
        return "needs-human"
    if sig.dimension_class == "mechanical" and sig.small:
        return "prod-safe"
    return "canary"


def clamp(floor: str, agent: str) -> str:
    """The agent may only make the recommendation SAFER (lower rank), never bolder than the floor.
    Always returns a canonical tier (never a raw/unknown string)."""
    if agent not in TIER_RANK:
        agent = "needs-human"
    agent_rank = TIER_RANK[agent]
    return floor if agent_rank >= TIER_RANK[floor] else agent
