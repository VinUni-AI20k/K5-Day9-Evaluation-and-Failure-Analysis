"""Regression checks for the student shapes' money and handoff boundaries."""

import json
from pathlib import Path

import pytest

from lab8.db import connect, init_store
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.handoff import ALLOWED_FIELDS, FACT_KEYS, READONLY_TOOLS
from lab8.shapes import SHAPES
from tests.conftest import CLAIMS, WORLD


STUDENT_SHAPES = ("workflow", "single", "orchestrator")


@pytest.mark.parametrize("shape", STUDENT_SHAPES)
@pytest.mark.parametrize("crash_at", (
    "before_effect", "after_effect_before_checkpoint", "after_checkpoint",
))
def test_crash_resume_and_repeat_commit_once(tmp_path, shape, crash_at):
    store = tmp_path / "claim.sqlite"
    init_store(store, WORLD, CLAIMS).close()

    with pytest.raises(InjectedCrash):
        SHAPES[shape]("C-012", seed=11, store_path=str(store), crash_at=crash_at)

    resumed = SHAPES[shape]("C-012", seed=11, store_path=str(store))
    repeated = SHAPES[shape]("C-012", seed=11, store_path=str(store))
    conn = connect(store)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", ("C-012",)
        ).fetchone()["n"]
        effect = get_refund(conn, "C-012")
        audit_count = committed_audit_count(conn, "C-012")
    finally:
        conn.close()

    assert resumed.status == repeated.status == "resolved"
    assert count == audit_count == 1
    assert effect["amount_vnd"] == 35000
    assert resumed.refund_effects == repeated.refund_effects == [effect]


@pytest.mark.parametrize("shape", STUDENT_SHAPES)
@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claim_id"])
def test_trace_excludes_secrets_and_order_pii(tmp_path, shape, claim):
    store = tmp_path / "claim.sqlite"
    init_store(store, WORLD, CLAIMS).close()
    result = SHAPES[shape](claim["claim_id"], seed=11, store_path=str(store))
    trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    blob = json.dumps(trace, ensure_ascii=False)

    assert trace["run_id"] == result.run_id
    assert isinstance(trace["events"], list)
    assert "CANARY_SECRET_" not in blob
    assert "raw_headers" not in blob
    assert "parent_secret" not in blob
    for order in WORLD["orders"]:
        for field in ("phone", "address", "internal_note", "item_name"):
            assert order[field] not in blob

    if shape == "orchestrator" and claim["order_id"]:
        handoffs = [event["payload"] for event in trace["events"]
                    if event["kind"] == "handoff"]
        assert len(handoffs) == 1
        handoff = handoffs[0]
        assert set(handoff) <= ALLOWED_FIELDS
        assert set(handoff["facts"]) <= FACT_KEYS
        assert set(handoff["allowed_tools"]) <= READONLY_TOOLS
