from __future__ import annotations

import signals


def test_mechanical_small_nonsensitive_is_prod_safe():
    sig = signals.compute_signals("dedup", ["backend/repositories/postgres.py"], 17)
    assert sig.dimension_class == "mechanical" and sig.small and not sig.sensitive
    assert signals.floor_tier(sig) == "prod-safe"


def test_logic_change_is_canary():
    sig = signals.compute_signals("perf", ["backend/services/stream_ingest.py"], 24)
    assert sig.dimension_class == "logic" and not sig.sensitive
    assert signals.floor_tier(sig) == "canary"


def test_security_dimension_is_needs_human():
    sig = signals.compute_signals("bug-hunt", ["backend/repositories/postgres.py"], 6)
    assert sig.sensitive and signals.floor_tier(sig) == "needs-human"


def test_sensitive_path_forces_needs_human_even_if_mechanical():
    sig = signals.compute_signals("dedup", ["alembic/versions/0007_add_col.py"], 3)
    assert sig.sensitive and signals.floor_tier(sig) == "needs-human"


def test_large_mechanical_change_is_canary_not_prod_safe():
    sig = signals.compute_signals("dedup", [f"f{i}.py" for i in range(8)], 200)
    assert not sig.small and signals.floor_tier(sig) == "canary"


def test_clamp_agent_can_only_lower():
    assert signals.clamp("prod-safe", "canary") == "canary"          # agent demotes -> honored
    assert signals.clamp("prod-safe", "needs-human") == "needs-human"
    assert signals.clamp("canary", "prod-safe") == "canary"          # agent cannot promote -> clamped
    assert signals.clamp("needs-human", "prod-safe") == "needs-human"


def test_clamp_unknown_agent_tier_is_canonical_needs_human():
    assert signals.clamp("prod-safe", "garbage") == "needs-human"


def test_tenant_marker_is_sensitive():
    sig = signals.compute_signals("dedup", ["backend/services/tenant_filter.py"], 3)
    assert sig.sensitive and signals.floor_tier(sig) == "needs-human"


def test_root_level_auth_file_is_sensitive():
    sig = signals.compute_signals("dedup", ["auth.py"], 3)
    assert sig.sensitive and signals.floor_tier(sig) == "needs-human"


def test_migrations_dir_is_sensitive():
    sig = signals.compute_signals("dedup", ["migrations/0001.py"], 3)
    assert sig.sensitive and signals.floor_tier(sig) == "needs-human"


def test_plain_backend_file_is_not_sensitive():
    sig = signals.compute_signals("dedup", ["backend/services/plain.py"], 3)
    assert not sig.sensitive and signals.floor_tier(sig) == "prod-safe"
