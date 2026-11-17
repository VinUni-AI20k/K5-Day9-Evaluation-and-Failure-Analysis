"""Ledger + approval gate: crash points and denial branches not covered elsewhere.

Each test builds its own order / claim / approval rows so it does not depend on
which public claim happens to have which approval.
"""

import pytest

from lab8.db import connect
from lab8.durability import InjectedCrash, committed_audit_count, get_refund, issue_refund


def _add_order(conn, order_id, *, principal="P-100", paid=500000):
    conn.execute(
        """
        INSERT INTO orders (order_id, principal_id, status, delay_days, shipping_fee_vnd, paid_vnd,
                            damage_verified, carrier, phone, address, internal_note, item_name)
        VALUES (?, ?, 'delivered', 3, 35000, ?, 0, 'TEST', '0000000000', 'test', 'test', 'test')
        """,
        (order_id, principal, paid),
    )


def _add_claim(conn, claim_id, order_id, approval_id, *, principal="P-100"):
    conn.execute(
        """
        INSERT INTO claims (claim_id, principal_id, order_id, ticket, parent_secret, raw_headers_json, approval_id)
        VALUES (?, ?, ?, 'test', 'CANARY_SECRET_PARENT_LEDGER', '{}', ?)
        """,
        (claim_id, principal, order_id, approval_id),
    )


def _add_approval(conn, approval_id, claim_id, amount, *, status="valid", expires="2027-12-31"):
    conn.execute(
        "INSERT INTO approvals (approval_id, claim_id, approved_vnd, status, expires_at) VALUES (?, ?, ?, ?, ?)",
        (approval_id, claim_id, amount, status, expires),
    )


def _setup(conn, claim_id, *, approved=35000, paid=500000, status="valid", expires="2027-12-31"):
    order_id = f"O-{claim_id}"
    approval_id = f"A-{claim_id}"
    _add_order(conn, order_id, paid=paid)
    _add_approval(conn, approval_id, claim_id, approved, status=status, expires=expires)
    _add_claim(conn, claim_id, order_id, approval_id)
    conn.commit()


def _ledger_rows(conn, claim_id):
    return conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", (claim_id,)).fetchone()["n"]


def _checkpoint(conn, claim_id):
    return conn.execute(
        "SELECT 1 FROM checkpoints WHERE claim_id = ? AND step = 'issue_refund'", (claim_id,)
    ).fetchone()


# --- crash points -----------------------------------------------------------


def test_crash_before_effect_writes_nothing_then_resume_pays_once(public_db):
    conn = connect(public_db)
    _setup(conn, "C-LG1")
    with pytest.raises(InjectedCrash):
        issue_refund(conn, "C-LG1", 35000, crash_at="before_effect")
    assert get_refund(conn, "C-LG1") is None
    assert committed_audit_count(conn, "C-LG1") == 0

    resumed = issue_refund(conn, "C-LG1", 35000)
    assert resumed["reason"] == "committed"
    assert _ledger_rows(conn, "C-LG1") == 1
    assert committed_audit_count(conn, "C-LG1") == 1
    assert _checkpoint(conn, "C-LG1") is not None
    conn.close()


def test_crash_after_checkpoint_resume_is_replay(public_db):
    conn = connect(public_db)
    _setup(conn, "C-LG2")
    with pytest.raises(InjectedCrash):
        issue_refund(conn, "C-LG2", 35000, crash_at="after_checkpoint")
    assert _checkpoint(conn, "C-LG2") is not None

    resumed = issue_refund(conn, "C-LG2", 35000)
    assert resumed["reason"] == "idempotent_replay"
    assert _ledger_rows(conn, "C-LG2") == 1
    assert committed_audit_count(conn, "C-LG2") == 1
    conn.close()


@pytest.mark.parametrize("point", ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"])
def test_repeated_crashes_at_same_point_never_duplicate(public_db, point):
    """Crash three times in a row, then resume: still exactly one refund."""
    conn = connect(public_db)
    _setup(conn, "C-LG3")
    for _ in range(3):
        try:
            issue_refund(conn, "C-LG3", 35000, crash_at=point)
        except InjectedCrash:
            pass
    final = issue_refund(conn, "C-LG3", 35000)
    assert final["ok"] is True
    assert _ledger_rows(conn, "C-LG3") == 1
    assert committed_audit_count(conn, "C-LG3") == 1
    assert int(get_refund(conn, "C-LG3")["amount_vnd"]) == 35000
    conn.close()


# --- approval gate ----------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"expires": "2020-01-01"}, "approval_expired"),
        ({"status": "revoked"}, "approval_revoked"),
        ({"status": "pending"}, "approval_pending"),
        ({"approved": 0}, "non_positive_amount"),
    ],
)
def test_bad_approval_never_writes_and_is_audited(public_db, kwargs, reason):
    conn = connect(public_db)
    _setup(conn, "C-LG4", **kwargs)
    for _ in range(2):  # retry must not slip past the gate either
        outcome = issue_refund(conn, "C-LG4", 35000)
        assert outcome["ok"] is False
        assert outcome["reason"] == reason
    assert get_refund(conn, "C-LG4") is None
    assert committed_audit_count(conn, "C-LG4") == 0
    denied = conn.execute(
        "SELECT COUNT(*) AS n FROM audit_events WHERE claim_id = 'C-LG4' AND event_type = 'policy_denied'"
    ).fetchone()["n"]
    assert denied == 1  # INSERT OR IGNORE: one audit row per (claim, reason)
    conn.close()


def test_approval_row_missing_from_table_is_missing_approval(public_db):
    conn = connect(public_db)
    _add_order(conn, "O-LG5")
    _add_claim(conn, "C-LG5", "O-LG5", "A-DOES-NOT-EXIST")
    conn.commit()
    outcome = issue_refund(conn, "C-LG5", 35000)
    conn.close()
    assert outcome["reason"] == "missing_approval"


def test_zero_or_negative_proposal_is_rejected(public_db):
    conn = connect(public_db)
    _setup(conn, "C-LG6")
    assert issue_refund(conn, "C-LG6", 0)["reason"] == "non_positive_amount"
    assert issue_refund(conn, "C-LG6", -5000)["reason"] == "non_positive_amount"
    assert get_refund(conn, "C-LG6") is None
    conn.close()


# --- caps -------------------------------------------------------------------


def test_amount_is_capped_at_approved_amount(public_db):
    """A model that inflates the quote still only gets what the approval allows."""
    conn = connect(public_db)
    _setup(conn, "C-LG7", approved=35000)
    outcome = issue_refund(conn, "C-LG7", 999999)
    conn.close()
    assert outcome["ok"] is True
    assert int(outcome["effect"]["amount_vnd"]) == 35000


def test_amount_is_capped_at_paid_amount(public_db):
    conn = connect(public_db)
    _setup(conn, "C-LG8", approved=200000, paid=50000)
    outcome = issue_refund(conn, "C-LG8", 200000)
    conn.close()
    assert outcome["ok"] is True
    assert int(outcome["effect"]["amount_vnd"]) == 50000


# --- scope ------------------------------------------------------------------


def test_unknown_claim_writes_nothing(public_db):
    conn = connect(public_db)
    outcome = issue_refund(conn, "C-NOPE", 35000)
    conn.close()
    assert outcome == {"ok": False, "reason": "unknown_claim", "effect": None, "conflict": False}


def test_order_of_another_principal_is_out_of_scope(public_db):
    conn = connect(public_db)
    _add_order(conn, "O-LG9", principal="P-OTHER")
    _add_approval(conn, "A-LG9", "C-LG9", 35000)
    _add_claim(conn, "C-LG9", "O-LG9", "A-LG9", principal="P-100")
    conn.commit()
    outcome = issue_refund(conn, "C-LG9", 35000)
    effect = get_refund(conn, "C-LG9")
    conn.close()
    assert outcome["reason"] == "outside_principal_scope"
    assert effect is None


def test_claim_without_order_is_denied(public_db):
    conn = connect(public_db)
    _add_approval(conn, "A-LG10", "C-LG10", 35000)
    _add_claim(conn, "C-LG10", None, "A-LG10")
    conn.commit()
    outcome = issue_refund(conn, "C-LG10", 35000)
    conn.close()
    assert outcome["reason"] == "missing_order"
