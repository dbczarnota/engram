from __future__ import annotations

from pathlib import Path

from scan_config import load_config
from discover import discover_candidates
from design import design_interfaces
from synthesize import synthesize_rfc
from publish import publish, rfc_path
from scan_report import render_report


def _log(msg: str) -> None:
    print(f"[architecture-scan] {msg}", flush=True)


def run(repo_root: Path, now: str, *, discover_fn=discover_candidates, design_fn=design_interfaces,
        synth_fn=synthesize_rfc, publish_fn=publish) -> Path:
    cfg = load_config(repo_root)
    db_path = repo_root / ".code-review-graph" / "graph.db"
    candidates = discover_fn(db_path, repo_root, paths=cfg.paths, min_lines=cfg.min_lines,
                             top_k=cfg.top_k)
    _log(f"discovery: {len(candidates)} candidate(s)")
    out_dir = repo_root / cfg.report_dir / "architecture-scan"

    results: list[dict] = []
    filed = 0
    for cand in candidates:
        if filed >= cfg.max_rfcs:
            _log("max-rfcs reached; stopping")
            break
        if rfc_path(cand, out_dir).exists():
            _log(f"  {cand.qualified_name}: RFC exists -> duplicate (skip design)")
            results.append({"candidate": cand.qualified_name, "file": cand.file, "lines": cand.lines,
                            "degree": cand.degree, "outcome": "duplicate",
                            "detail": str(rfc_path(cand, out_dir)), "recommendation": ""})
            continue
        _log(f"design x3: {cand.qualified_name}")
        proposals = design_fn(cand, repo_root)
        rfc = synth_fn(cand, proposals, repo_root)
        if not rfc.markdown:
            _log(f"  synth failed for {cand.qualified_name}; skipping")
            results.append({"candidate": cand.qualified_name, "file": cand.file, "lines": cand.lines,
                            "degree": cand.degree, "outcome": "skipped", "detail": "synth failed",
                            "recommendation": ""})
            continue
        outcome, detail = publish_fn(rfc, out_dir)
        if outcome == "filed":
            filed += 1
        _log(f"  -> {outcome}: {detail}")
        results.append({"candidate": cand.qualified_name, "file": cand.file, "lines": cand.lines,
                        "degree": cand.degree, "outcome": outcome, "detail": detail,
                        "recommendation": rfc.recommendation})

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = now.replace(" ", "-").replace(":", "")
    report_path = out_dir / f"scan-{stem}.md"
    report_path.write_text(render_report(repo_root.name, now, results), encoding="utf-8")
    return report_path
