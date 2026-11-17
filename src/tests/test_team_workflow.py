"""Test riêng của Người 1 cho shape workflow."""

from __future__ import annotations

import json

import pytest

from lab8.db import connect, init_store
from lab8.durability import InjectedCrash
from lab8.shapes.workflow import run_claim
from tests.conftest import CLAIMS, WORLD


def _store(tmp_path):
    path = tmp_path / "wf.sqlite"
    init_store(path, WORLD, CLAIMS).close()
    return str(path)


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_workflow_ignores_delay_written_in_ticket(tmp_path, seed):
    # C-002: ticket nói "trễ 5 ngày", order ghi 2 ngày -> phải denied ở MỌI seed (kể cả 55).
    result = run_claim("C-002", seed=seed, store_path=_store(tmp_path))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []


@pytest.mark.parametrize("claim_id", [row["claim_id"] for row in CLAIMS])
def test_workflow_trace_has_no_secret_or_ticket(tmp_path, claim_id):
    result = run_claim(claim_id, seed=11, store_path=_store(tmp_path))
    with open(result.trace_path, encoding="utf-8") as fh:
        body = json.load(fh)
    blob = json.dumps(body, ensure_ascii=False)
    assert body["run_id"] == result.run_id
    assert isinstance(body["events"], list)
    assert "CANARY_SECRET_" not in blob
    ticket = next(row["ticket"] for row in CLAIMS if row["claim_id"] == claim_id)
    assert ticket not in blob


def test_quote_zero_skips_host(tmp_path):
    # T02: quote = 0 -> denied và KHÔNG gọi issue_refund, nên không có audit nào của host.
    store = _store(tmp_path)
    result = run_claim("C-002", seed=11, store_path=store)
    conn = connect(store)
    try:
        audits = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_events WHERE claim_id = 'C-002'"
        ).fetchone()["n"]
    finally:
        conn.close()
    assert result.status == "denied"
    assert audits == 0


def test_crash_is_traced_and_reraised(tmp_path):
    # T12: crash phải thoát ra ngoài run_claim, trace của lần chạy đó có event "crash".
    store = _store(tmp_path)
    with pytest.raises(InjectedCrash):
        run_claim("C-012", seed=11, store_path=store, crash_at="after_effect_before_checkpoint")
    with open("traces/R-workflow-C-012-s11.json", encoding="utf-8") as fh:
        kinds = [event["kind"] for event in json.load(fh)["events"]]
    assert kinds[-1] == "crash"


def test_workflow_t14_passes_full_quote_host_pays_difference(tmp_path):
    store = _store(tmp_path)
    result = run_claim("C-014", seed=11, store_path=store)
    assert result.status == "resolved"
    assert result.proposal_amount == 150000  # quote đầy đủ
    conn = connect(store)
    try:
        amount = conn.execute(
            "SELECT amount_vnd FROM refund_ledger WHERE claim_id = 'C-014'"
        ).fetchone()["amount_vnd"]
    finally:
        conn.close()
    assert amount == 120000  # host tự trừ 30.000 đã hoàn trước
