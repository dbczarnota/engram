from __future__ import annotations

import consolidate


def _fix(fp, br):
    return {"fingerprint": fp, "branch": br}


def test_consolidate_keeps_green_pulls_red_flags_conflict(tmp_path):
    events = []
    merged = []   # branches currently merged into the (fake) bundle

    def open_bundle(repo, name): return tmp_path / name
    def setup_bundle(cfg, wt): return (True, "ok")
    def try_merge(wt, br):
        if br == "fix/conflict":
            return False
        merged.append(br); return True
    def head_sha(wt): return "|".join(merged)                 # a marker of the current bundle state
    reverted_to = []
    def revert_last(wt, to_sha): reverted_to.append(to_sha); merged.pop()
    # fix/bad breaks the bundle (red) once merged; others are green
    def verify_green(cfg, wt): return (("fix/bad" not in merged), "boom" if "fix/bad" in merged else "green")
    def finalize(repo, wt, branch): return "sha123" if merged else None
    def close_bundle(repo, wt): events.append("closed")

    fixes = [_fix("a", "fix/a"), _fix("bad", "fix/bad"), _fix("c", "fix/c"), _fix("x", "fix/conflict")]
    res = consolidate.consolidate(
        tmp_path, object(), "prod-safe", fixes,
        open_bundle=open_bundle, setup_bundle=setup_bundle, try_merge=try_merge, revert_last=revert_last,
        head_sha=head_sha, verify_green=verify_green, finalize=finalize, close_bundle=close_bundle)
    assert reverted_to == ["fix/a"]                            # bad reverted to the pre-merge (a) state

    assert res.tier == "prod-safe" and res.branch == "sha123"
    assert [f["fingerprint"] for f in res.included] == ["a", "c"]   # bad pulled, conflict excluded
    assert [f["fingerprint"] for f in res.pulled] == ["bad"]
    assert [f["fingerprint"] for f in res.conflicts] == ["x"]
    assert "closed" in events                                       # worktree always closed


def test_consolidate_setup_failure_pulls_all(tmp_path):
    res = consolidate.consolidate(
        tmp_path, object(), "canary", [{"fingerprint": "a", "branch": "fix/a"}],
        open_bundle=lambda r, n: tmp_path, setup_bundle=lambda cfg, wt: (False, "uv sync failed"),
        try_merge=lambda wt, br: True, revert_last=lambda wt, to: None, head_sha=lambda wt: "x",
        verify_green=lambda cfg, wt: (True, "g"), finalize=lambda r, wt, b: None,
        close_bundle=lambda r, wt: None)
    assert res.branch is None and [f["fingerprint"] for f in res.pulled] == ["a"]
