from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_TEST_MARKERS = ("/tests/", "tests/", "conftest.py")


def _is_test_file(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]
    if not base.endswith(".py"):
        return True                       # non-python -> not a coverable prod source line
    return (any(m in p for m in _TEST_MARKERS) or base.startswith("test_")
            or base.endswith("_test.py") or base == "conftest.py")


def parse_cobertura(xml_text: str) -> dict[str, dict[int, int]]:
    out: dict[str, dict[int, int]] = {}
    root = ET.fromstring(xml_text)
    for cls in root.iter("class"):
        fname = (cls.get("filename") or "").replace("\\", "/")
        if not fname:
            continue
        lines = out.setdefault(fname, {})
        for ln in cls.iter("line"):
            try:
                lines[int(ln.get("number"))] = int(ln.get("hits") or 0)
            except (TypeError, ValueError):
                continue
    return out


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def added_prod_lines(diff_text: str) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    cur_file: str | None = None
    new_line = 0
    for row in diff_text.splitlines():
        if row.startswith("+++ "):
            path = row[4:].strip()
            path = path[2:] if path.startswith("b/") else path      # strip the "b/" prefix
            cur_file = None if _is_test_file(path) else path.replace("\\", "/")
            continue
        if row.startswith("@@"):
            m = _HUNK.match(row)
            new_line = int(m.group(1)) if m else new_line
            continue
        if cur_file is None:
            continue
        if row.startswith("+") and not row.startswith("+++"):
            out.setdefault(cur_file, set()).add(new_line)
            new_line += 1
        elif row.startswith("-") and not row.startswith("---"):
            pass                                                    # removed line: new-file counter unaffected
        else:
            new_line += 1                                           # context line advances the new file
    return out


def _match_coverage(fname: str, cov: dict[str, dict[int, int]]) -> dict[int, int] | None:
    """Find the coverage entry for a changed file. Handles the common path-base mismatch where the diff
    path is repo-relative (`backend/a.py`) but cobertura's `filename` is relative to `--cov`'s root
    (`a.py`): match on exact path or a path-segment suffix either way. Returns None if the file is not
    measured at all (→ caller treats it as UNCOVERED, fail-safe)."""
    f = fname.replace("\\", "/")
    if f in cov:
        return cov[f]
    for k, lines in cov.items():
        kk = k.replace("\\", "/")
        if kk == f or f.endswith("/" + kk) or kk.endswith("/" + f):
            return lines
    return None


def fully_covered(added: dict[str, set[int]], cov: dict[str, dict[int, int]]) -> bool:
    """True iff every changed prod file is MEASURED by coverage and each of its added executable lines is
    hit. Fails SAFE: a changed file absent from the coverage map (unmeasured / path mismatch / a new file
    no test imports) counts as NOT covered → returns False → the caller demotes prod-safe to canary."""
    for fname, lines in added.items():
        file_cov = _match_coverage(fname, cov)
        if file_cov is None:                                        # unmeasured file -> fail-safe uncovered
            return False
        for ln in lines:
            if ln in file_cov and file_cov[ln] == 0:                # executable AND unhit -> uncovered
                return False
    return True
