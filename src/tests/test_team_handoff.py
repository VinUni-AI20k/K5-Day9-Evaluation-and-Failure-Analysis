import json
from pathlib import Path

import pytest

from lab8.handoff import HandoffError, READONLY_TOOLS, WRITE_TOOLS, make_handoff, sanitize
from lab8.shapes.orchestrator import run_claim


def test_handoff_filters_parent_context_and_limits_facts():
    handoff = make_handoff(
        request_id="REQ-C-001",
        claim_id="C-001",
        task="check_applicable_compensation",
        facts={"delay_days": 4, "parent_secret": "CANARY_SECRET_PARENT_C-001"},
        allowed_tools=["lookup_order", "compute_compensation"],
    )

    assert handoff["facts"] == {"delay_days": 4}
    assert set(handoff["allowed_tools"]) <= READONLY_TOOLS
    assert not set(handoff["allowed_tools"]) & WRITE_TOOLS
    assert "CANARY_SECRET_" not in json.dumps(handoff)
    assert "parent_secret" not in handoff


def test_handoff_rejects_write_tools_and_canaries_in_allowed_fields():
    with pytest.raises(HandoffError):
        make_handoff(
            request_id="REQ-C-001",
            claim_id="C-001",
            task="pay",
            facts={},
            allowed_tools=["issue_refund"],
        )

    with pytest.raises(HandoffError):
        sanitize({"task": "CANARY_SECRET_PARENT_C-001"})


def test_orchestrator_trace_for_out_of_scope_order_is_sanitized(public_db):
    result = run_claim("C-005", seed=11, store_path=str(public_db))
    trace_path = Path(result.trace_path)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace_text = json.dumps(trace, ensure_ascii=False)

    assert result.status == "escalated"
    assert result.proposal_amount == 0
    assert trace["run_id"] == result.run_id
    assert isinstance(trace["events"], list)
    assert "CANARY_SECRET_" not in trace_text
    assert "Bearer " not in trace_text
    assert "0901111222" not in trace_text
    assert "99 Duong Bi Mat" not in trace_text
    assert "SECRET_ITEM_VANG" not in trace_text
    assert "CANARY_INTERNAL_O110" not in trace_text

    handoff_event = next(event for event in trace["events"] if event["kind"] == "handoff")
    allowed_tools = set(handoff_event["payload"]["allowed_tools"])
    assert allowed_tools <= READONLY_TOOLS
    assert not allowed_tools & WRITE_TOOLS
