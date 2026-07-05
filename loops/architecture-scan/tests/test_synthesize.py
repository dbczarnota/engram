import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from synthesize import synthesize_rfc
from models import Candidate, DesignProposal, RFC


def test_builds_rfc_from_agent(tmp_path):
    cand = Candidate("r::run", "loops/fix-loop/runner.py", 34, 168, 135, 172, ["large-function"], 651.0)
    props = [DesignProposal("phase-pipeline", "i1", "d1", "w1"),
             DesignProposal("strategy-outcome", "i2", "d2", "w2"),
             DesignProposal("functional-core", "i3", "d3", "w3")]

    def fake_agent(candidate, proposals, repo_root):
        assert len(proposals) == 3
        return ("go with strategy-outcome", "# RFC: deepen run\n...")

    rfc = synthesize_rfc(cand, props, tmp_path, agent_fn=fake_agent)
    assert isinstance(rfc, RFC)
    assert rfc.recommendation == "go with strategy-outcome"
    assert rfc.markdown.startswith("# RFC")
    assert rfc.candidate is cand
