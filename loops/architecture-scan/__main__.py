from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))               # our own modules win
_REVIEW_LOOP = _HERE.parent / "review-loop"
if str(_REVIEW_LOOP) not in sys.path:
    sys.path.append(str(_REVIEW_LOOP))           # reuse claude_iterate helpers

from cli import main  # noqa: E402

if __name__ == "__main__":
    main()
