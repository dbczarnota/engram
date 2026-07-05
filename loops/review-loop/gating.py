from __future__ import annotations

from config import ReviewLoopConfig

# MVP enables bug-hunt only in the iteration prompt, but gating already knows the
# full dimension set so later plans (2+) flip them on without touching this logic.
_ALWAYS = ["bug-hunt", "security", "consistency", "dedup", "complexity", "perf", "dead-code"]


def enabled_dimensions(cfg: ReviewLoopConfig) -> list[str]:
    dims = list(_ALWAYS)
    if cfg.logfire:
        dims.append("log-sweep")
    return dims


def enabled_layers(cfg: ReviewLoopConfig) -> list[tuple[str, list[str]]]:
    """Which layers the LLM pass reviews, each with its globs. A repo with no frontend globs
    skips the frontend layer; a repo that configures neither gets one whole-repo `all` pass."""
    layers: list[tuple[str, list[str]]] = []
    if cfg.backend:
        layers.append(("backend", list(cfg.backend)))
    if cfg.frontend:
        layers.append(("frontend", list(cfg.frontend)))
    if not layers:
        layers.append(("all", []))
    return layers
