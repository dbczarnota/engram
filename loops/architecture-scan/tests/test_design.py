import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import design_interfaces, PHILOSOPHIES
from models import Candidate, DesignProposal


def _cand():
    return Candidate("r::run", "loops/fix-loop/runner.py", 34, 168, 135, 172, ["large-function"], 651.0)


def test_runs_three_distinct_philosophies(tmp_path):
    seen = []

    def fake_agent(cand, key, philosophy, repo_root):
        seen.append(key)
        return DesignProposal(philosophy=key, interface=f"iface-{key}",
                              deep_modules="dm", weakness="w", ok=True)

    props = design_interfaces(_cand(), tmp_path, agent_fn=fake_agent)
    assert len(props) == 3
    assert sorted(p.philosophy for p in props) == sorted(k for k, _ in PHILOSOPHIES)
    assert sorted(seen) == sorted(k for k, _ in PHILOSOPHIES)


def test_failed_agent_marked_not_ok(tmp_path):
    def fake_agent(cand, key, philosophy, repo_root):
        return DesignProposal(philosophy=key, interface="", deep_modules="", weakness="", ok=False)

    props = design_interfaces(_cand(), tmp_path, agent_fn=fake_agent)
    assert all(not p.ok for p in props)
