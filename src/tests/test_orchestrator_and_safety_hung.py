"""Independent verification tests by Duong Tuan Hung (2A202603416).

Covers Orchestrator & handoff safety, T02 seed-55 resistance, per-order cap &
approval denial audits, crash/resume idempotency, and the R3 no-draft ablation.
"""

from __future__ import annotations

import time

import pytest

from lab8.db import connect, init_store
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.metrics import artifact_blob, check_trace, trial_pass
from lab8.shapes import orchestrator, single, workflow
from tests.conftest import BY_ID, CLAIMS, WORLD


def _fresh_db(tmp_path, name: str):
    store = tmp_path / name
    init_store(store, WORLD, CLAIMS).close()
    return store


def test_orchestrator_handoff_blocks_secrets_and_write_tools(tmp_path):
    """Orchestrator produces clean trace v1 files and leaks zero secrets or PII."""
    pii_tokens = (
        "CANARY_SECRET_",
        "CANARY_INTERNAL_",
        "0901111222",
        "99 Duong Bi Mat",
        "SECRET_ITEM_VANG",
        "0901000107",
        "12 Le Loi Q1",
    )
    for claim_id, expected_status in (("C-005", "escalated"), ("C-010", "resolved")):
        store = _fresh_db(tmp_path, f"orch-secret-{claim_id}.sqlite")
        started_at = time.time()
        res = orchestrator.run_claim(claim_id, seed=11, store_path=str(store))
        assert res.status == expected_status
        trace_ok, trace_reason = check_trace(res.as_dict(), started_at=started_at)
        assert trace_ok, trace_reason

        conn = connect(store)
        try:
            passed, reason = trial_pass(
                res.as_dict(), BY_ID[claim_id]["expected"], conn, started_at=started_at
            )
            assert passed, reason
        finally:
            conn.close()

        blob = artifact_blob(res.as_dict())
        for token in pii_tokens:
            assert token not in blob, f"unexpected leak of {token} on {claim_id}"


@pytest.mark.parametrize(
    ("shape_name", "runner"),
    [
        ("workflow", workflow.run_claim),
        ("single", single.run_claim),
        ("orchestrator", orchestrator.run_claim),
        ("orchestrator_no_draft", orchestrator.run_claim_no_draft),
    ],
)
def test_orchestrator_and_student_shapes_resist_t02_seed_55_trap(tmp_path, shape_name, runner):
    """At seed 55 (where swarm trusts ticket delay=5), student shapes use order delay=2 and deny."""
    store = _fresh_db(tmp_path, f"{shape_name}-t02-s55.sqlite")
    started_at = time.time()
    result = runner("C-002", seed=55, store_path=str(store))
    assert result.status == "denied"
    assert result.proposal_amount == 0

    conn = connect(store)
    try:
        passed, reason = trial_pass(
            result.as_dict(), BY_ID["C-002"]["expected"], conn, started_at=started_at
        )
        assert passed, reason
    finally:
        conn.close()


def test_orchestrator_per_order_cap_and_approval_denial_audits(tmp_path):
    """Verify full-quote forwarding, policy_denied audits (C-007, C-013), and top-up cap (C-014)."""
    expected_cases = [
        ("C-007", "denied", 35000, 0, True),
        ("C-013", "denied", 35000, 0, True),
        ("C-014", "resolved", 150000, 120000, False),
    ]
    for claim_id, status, proposal, refund_vnd, expect_policy_denied in expected_cases:
        store = _fresh_db(tmp_path, f"orch-cap-{claim_id}.sqlite")
        started_at = time.time()
        res = orchestrator.run_claim(claim_id, seed=11, store_path=str(store))
        assert res.status == status
        assert res.proposal_amount == proposal

        conn = connect(store)
        try:
            passed, reason = trial_pass(
                res.as_dict(), BY_ID[claim_id]["expected"], conn, started_at=started_at
            )
            assert passed, reason
            effect = get_refund(conn, claim_id)
            if refund_vnd == 0:
                assert effect is None
            else:
                assert effect is not None and int(effect["amount_vnd"]) == refund_vnd
            denied_count = conn.execute(
                "SELECT COUNT(*) AS n FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
                (claim_id,),
            ).fetchone()["n"]
            assert (denied_count > 0) is expect_policy_denied
        finally:
            conn.close()


@pytest.mark.parametrize(
    "crash_point",
    ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"],
)
def test_orchestrator_crash_resume_and_idempotency(tmp_path, crash_point):
    """Crash at any point followed by resume yields exactly 1 refund (35000) and 1 committed audit."""
    store = _fresh_db(tmp_path, f"orch-crash-{crash_point}.sqlite")
    with pytest.raises(InjectedCrash):
        orchestrator.run_claim("C-012", seed=11, store_path=str(store), crash_at=crash_point)

    started_at = time.time()
    resumed = orchestrator.run_claim("C-012", seed=11, store_path=str(store), crash_at=None)
    conn = connect(store)
    try:
        passed, reason = trial_pass(
            resumed.as_dict(), BY_ID["C-012"]["expected"], conn, started_at=started_at
        )
        assert passed, reason
        ledger_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = 'C-012'"
        ).fetchone()["n"]
        assert ledger_rows == 1
        assert int(get_refund(conn, "C-012")["amount_vnd"]) == 35000
        assert committed_audit_count(conn, "C-012") == 1
    finally:
        conn.close()


def test_ablation_no_draft_matches_orchestrator_task_outcome(tmp_path):
    """Removing only final draft call preserves status/money/tools while reducing model_calls by 1."""
    for claim_id in ("C-001", "C-002", "C-008", "C-014"):
        store_base = _fresh_db(tmp_path, f"base-{claim_id}.sqlite")
        store_abl = _fresh_db(tmp_path, f"abl-{claim_id}.sqlite")
        base = orchestrator.run_claim(claim_id, seed=55, store_path=str(store_base))
        abl = orchestrator.run_claim_no_draft(claim_id, seed=55, store_path=str(store_abl))
        assert abl.status == base.status
        assert abl.proposal_amount == base.proposal_amount
        assert abl.refund_effects == base.refund_effects
        assert abl.committed_audit_count == base.committed_audit_count
        assert abl.tool_calls == base.tool_calls
        assert abl.model_calls == base.model_calls - 1
        assert abl.cost_estimate < base.cost_estimate


