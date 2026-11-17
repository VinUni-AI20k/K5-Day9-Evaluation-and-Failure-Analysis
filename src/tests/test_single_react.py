import json
from pathlib import Path

import pytest

from lab8.runtime import run_react
from lab8.shapes import single


@pytest.mark.student
def test_single_stops_at_react_step_cap(public_db, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def keep_reading(conn, budget, *, observation, decide, max_steps, worker):
        assert worker is True

        def repeat_first_action(_observation):
            return decide(observation)

        return run_react(
            conn,
            budget,
            observation=observation,
            decide=repeat_first_action,
            max_steps=max_steps,
            worker=worker,
        )

    def unexpected_refund(*args, **kwargs):
        pytest.fail("The host must not be called after the ReAct step cap")

    monkeypatch.setattr(single, "run_react", keep_reading)
    monkeypatch.setattr(single, "issue_refund", unexpected_refund)
    result = single.run_claim("C-001", seed=11, store_path=str(public_db))

    assert result.status == "failed"
    assert result.error_reason == "step_cap"
    assert result.model_calls == result.tool_calls == 8
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert result.committed_audit_count == 0
    trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert trace["run_id"] == result.run_id
    assert trace["events"][-1]["payload"]["reason"] == "step_cap"
