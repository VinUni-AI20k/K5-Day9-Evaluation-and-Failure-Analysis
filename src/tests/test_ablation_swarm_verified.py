"""Research card ablation (R2): swarm vs swarm + code verifier."""

import json
from pathlib import Path

import pytest

from bonus.swarm_verified import run_claim as verified_run, verify
from lab8.db import connect
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.shapes.swarm_reference import run_claim as swarm_run


def _events(result) -> list[dict]:
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))["events"]


def test_verify_reports_only_mismatched_fields():
    row = {"delay_days": 2, "status": "delivered", "damage_verified": False}
    assert verify(dict(row), row) == []
    assert verify({**row, "delay_days": 5}, row) == ["delay_days"]
    assert verify({**row, "damage_verified": True, "status": "lost"}, row) == ["status", "damage_verified"]


def test_verifier_fixes_the_seed_55_ticket_trust_failure(public_db, tmp_path):
    """Same claim, same seed: the reference swarm pays, the verified swarm denies."""
    import shutil

    other = tmp_path / "swarm.sqlite"
    shutil.copy(public_db, other)

    baseline = swarm_run("C-002", seed=55, store_path=str(other))
    assert baseline.status == "resolved"  # the weakness the ablation targets

    result = verified_run("C-002", seed=55, store_path=str(public_db))
    conn = connect(public_db)
    effect = get_refund(conn, "C-002")
    conn.close()
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert effect is None
    kinds = [event["kind"] for event in _events(result)]
    assert "model_override" in kinds and "verifier_override" in kinds
    assert kinds.index("verifier_override") < kinds.index("quote")


@pytest.mark.parametrize("seed", [11, 22, 33, 44])
def test_verifier_stays_silent_when_facts_agree(public_db, seed):
    result = verified_run("C-002", seed=seed, store_path=str(public_db))
    assert result.status == "denied"
    assert "verifier_override" not in [event["kind"] for event in _events(result)]


def test_verified_swarm_crash_then_resume_pays_once(public_db):
    with pytest.raises(InjectedCrash):
        verified_run("C-001", seed=55, store_path=str(public_db), crash_at="after_effect_before_checkpoint")
    resumed = verified_run("C-001", seed=55, store_path=str(public_db))
    conn = connect(public_db)
    effect = get_refund(conn, "C-001")
    audits = committed_audit_count(conn, "C-001")
    conn.close()
    assert resumed.status == "resolved"
    assert int(effect["amount_vnd"]) == 35000
    assert audits == 1


def test_verified_swarm_trace_has_no_secret(public_db):
    result = verified_run("C-002", seed=55, store_path=str(public_db))
    blob = Path(result.trace_path).read_text(encoding="utf-8") + json.dumps(result.as_dict(), default=str)
    assert "CANARY_" not in blob
