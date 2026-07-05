from __future__ import annotations

import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
sys.path.append(str(_HERE.parent / "review-loop"))   # registry/config/claude helpers
sys.path.append(str(_HERE.parent / "fix-loop"))      # fix_config + baseline (setup/verify) reuse

from runner import run  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python __main__.py <repo-path>")
        raise SystemExit(2)
    repo = Path(sys.argv[1]).resolve()
    report = run(repo, time.strftime("%Y-%m-%d %H%M"))
    print(f"integrate-loop done. Report: {report}")


if __name__ == "__main__":
    main()
