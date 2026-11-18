"""Regression tests for FM-08 (ReplyMatchesLedger) and the M3 trace case (C-002@11)."""
import pytest

pytestmark = pytest.mark.student


def _ctx(trial, label=None):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(
        name="t",
        inputs={},
        metadata=None,
        expected_output=label or {"refund_vnd": 20000, "approval_ok": True, "policy_denied": False},
        output=trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


def test_reply_matches_ledger_catches_fm08():
    from lab9 import graders

    bad_trial = {
        "snapshot": {"refund_vnd": 20000, "refund_count": 1, "policy_denied": False},
        "unexpected_rows": 0,
        "blob": "",
        "events": [{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}}],
        "result": {},
        "lab8_pass": True,
        "lab8_reason": None,
    }
    res = graders.ReplyMatchesLedger().evaluate(_ctx(bad_trial))
    assert res.value is False
    assert "35000!=ledger=20000" in (res.reason or "")

    good_trial = {**bad_trial, "events": [{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808."}}]}
    assert graders.ReplyMatchesLedger().evaluate(_ctx(good_trial)).value is True


def test_trace_case_c002_seed11_regression_vs_fixed():
    from lab9 import graders, trace_case

    bad = trace_case.investigate("seeded_regression", "C-002", 11)
    bad_ctx = _ctx(bad["trial"], bad["label"])
    assert graders.DbFactKept().evaluate(bad_ctx).value is False
    assert graders.RefundAmountCorrect().evaluate(bad_ctx).value is False

    good = trace_case.investigate("fixed", "C-002", 11)
    good_ctx = _ctx(good["trial"], good["label"])
    assert graders.DbFactKept().evaluate(good_ctx).value is True
    assert graders.RefundAmountCorrect().evaluate(good_ctx).value is True
