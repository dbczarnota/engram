from __future__ import annotations

import os
from pathlib import Path

from models import RFC, Candidate


def _slug(candidate: Candidate) -> str:
    raw = candidate.qualified_name.split("::")[-1] + "-" + candidate.file
    return "".join(c if c.isalnum() else "-" for c in raw)[:50].strip("-")


def rfc_path(candidate: Candidate, out_dir: Path) -> Path:
    """Return the filepath where an RFC for this candidate should be written."""
    return Path(out_dir) / f"rfc-deepen-{_slug(candidate)}.md"


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def publish(rfc: RFC, out_dir: Path) -> tuple[str, str]:
    """Write the RFC as a markdown file in the vault report dir (same scheme + place as review-loop
    reports). Dedup by filename: one RFC per candidate; a re-run whose file already exists returns
    ('duplicate', path) and leaves it untouched."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = rfc_path(rfc.candidate, out_dir)
    if path.exists():
        return ("duplicate", str(path))
    sym = rfc.candidate.qualified_name.split("::")[-1]
    header = (f"# RFC: deepen `{sym}` ({rfc.candidate.file})\n\n"
              f"> **Recommendation:** {rfc.recommendation}\n\n")
    _atomic_write(path, header + rfc.markdown)
    return ("filed", str(path))
