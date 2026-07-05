import sys
from pathlib import Path

# fix-loop reuses review-loop modules (registry / verify / adversarial / worktree / claude helpers,
# and report.Finding). fix-loop's own modules are named fix_config / fix_report to avoid shadowing
# review-loop's config / report on the shared sys.path — so we only add review-loop here.
_REVIEW_LOOP = Path(__file__).resolve().parent.parent.parent / "review-loop"
if str(_REVIEW_LOOP) not in sys.path:
    # append (not insert(0)): both dirs have a runner.py — fix-loop's own must win over
    # review-loop's for "import runner" (the cwd's fix-loop dir is already sys.path[0] via
    # `python -m pytest`). Everything else review-loop provides is uniquely named.
    sys.path.append(str(_REVIEW_LOOP))
