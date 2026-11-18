"""Unit tests for M3 FM-08 (ReplyLedgerMatch) and step proposal consistency (ProposalMatchesQuote)."""

import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9 import graders

pytestmark = pytest.mark.student


def _ctx(trial: dict) -> EvaluatorContext:
    return EvaluatorContext(
        name="t",
        inputs={},
        metadata=None,
        expected_output={"refund_vnd": 20000, "approval_ok": True, "forbid_substrings": []},
        output=trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


def _trial(*, refund_vnd=20000, proposal_amount=35000, events=()):
    return {
        "snapshot": {"refund_vnd": refund_vnd, "refund_count": 1 if refund_vnd else 0},
        "unexpected_rows": 0,
        "blob": "",
        "events": list(events),
        "result": {"proposal_amount": proposal_amount},
        "lab8_pass": True,
        "lab8_reason": None,
    }


def test_reply_ledger_match_passes_when_matching_or_no_reply():
    ev = graders.ReplyLedgerMatch()
    assert ev.evaluate(_ctx(_trial(refund_vnd=20000, events=[]))).value is True
    assert ev.evaluate(
        _ctx(_trial(refund_vnd=20000, events=[{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808. Tiền về trong 3–5 ngày ạ."}}]))
    ).value is True
    assert ev.evaluate(
        _ctx(_trial(refund_vnd=0, events=[{"kind": "reply", "payload": {"text": "Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."}}]))
    ).value is True


def test_reply_ledger_match_catches_fm08_misreport():
    ev = graders.ReplyLedgerMatch()
    assert ev.evaluate(
        _ctx(_trial(refund_vnd=20000, events=[{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}}]))
    ).value is False
    assert ev.evaluate(
        _ctx(_trial(refund_vnd=0, events=[{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35000 VND cho đơn O-909."}}]))
    ).value is False


def test_proposal_matches_quote_catches_prededuct_and_sum_parts():
    ev = graders.ProposalMatchesQuote()
    ok = _trial(proposal_amount=35000, events=[{"kind": "quote", "payload": {"amount_vnd": 35000}}])
    bad = _trial(proposal_amount=0, events=[{"kind": "quote", "payload": {"amount_vnd": 35000}}])
    assert ev.evaluate(_ctx(ok)).value is True
    assert ev.evaluate(_ctx(bad)).value is False