import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent          # loops/integrate-loop
sys.path.insert(0, str(_HERE))
sys.path.append(str(_HERE.parent / "review-loop"))      # registry/config/claude_iterate helpers
sys.path.append(str(_HERE.parent / "fix-loop"))     # worktree + baseline (setup/verify) reuse
