from integrate_report import render_integrate_report


def test_report_groups_by_tier_with_rationale():
    decisions = [
        {"fingerprint": "a.py:foo:dup", "dimension": "dedup", "branch": "fix/a",
         "tier": "prod-safe", "rationale": "mechanical, covered", "signals": "small"},
        {"fingerprint": "b.py:bar:n1", "dimension": "perf", "branch": "fix/b",
         "tier": "canary", "rationale": "query change — watch", "signals": "logic"},
        {"fingerprint": "c.py:baz:org", "dimension": "bug-hunt", "branch": "fix/c",
         "tier": "needs-human", "rationale": "tenant filter — human review", "signals": "sensitive"},
    ]
    txt = render_integrate_report("demo", "2026-07-03 2100", decisions=decisions)
    assert "prod-safe: 1" in txt and "canary: 1" in txt and "needs-human: 1" in txt
    assert "fix/a" in txt and "query change — watch" in txt and "tenant filter" in txt
    assert "You are the gate" in txt


def test_report_renders_bundles_section():
    decisions = [
        {"fingerprint": "a.py:foo:dup", "dimension": "dedup", "branch": "fix/a",
         "tier": "prod-safe", "rationale": "mechanical, covered", "signals": "small"},
    ]
    bundles = [{"tier": "prod-safe", "branch": "integrate/prod-safe", "included": 1, "pulled": 0,
                "conflicts": 0},
               {"tier": "canary", "branch": None, "included": 0, "pulled": 1, "conflicts": 0}]
    txt = render_integrate_report("demo", "2026-07-03 2100", decisions=decisions, bundles=bundles)
    assert "## Bundles" in txt
    assert "integrate/prod-safe" in txt
    assert "included 1" in txt
    assert "canary" in txt and "(none — nothing shippable)" in txt
