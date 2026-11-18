"""Regression tests born from trace cases (docs/trace_case.md) and the FM-08 metric (M3)."""
import pytest

pytestmark = pytest.mark.student


def _ctx(trial, label):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def _trial(refund_vnd, reply=None):
    events = [] if reply is None else [{"kind": "reply", "payload": {"text": reply}}]
    return {"snapshot": {"refund_vnd": refund_vnd, "refund_count": int(refund_vnd > 0)},
            "unexpected_rows": 0, "blob": "", "events": events, "result": {}, "lab8_pass": True, "lab8_reason": None}


@pytest.mark.parametrize("ledger,reply,ok", [
    (20000, "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.", False),   # C-008 under seeded_regression
    (0, "Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.", False),       # C-007: host denied, reply says paid
    (20000, "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.", True),
    (150000, "LogiX đã hoàn phí 150.000đ cho đơn O-303 của anh/chị ạ.", True),   # paraphrase
    (0, "Dạ, đơn O-606 chưa đủ điều kiện hoàn theo chính sách hiện hành.", True),
    (35000, None, True),                                           # swarm writes no reply event
])
def test_reply_matches_ledger(ledger, reply, ok):
    from lab9.graders import ReplyMatchesLedger

    assert ReplyMatchesLedger().evaluate(_ctx(_trial(ledger, reply), {})).value is ok


def _run(shape, claim, seed):
    from lab9.trace_case import investigate

    case = investigate(shape, claim, seed)
    return _ctx(case["trial"], case["label"])


def test_trace_case_c002_ticket_trust():
    """Trace case: seeded_regression C-002@11, first wrong step = event 3 model_override (FM-03)."""
    from lab9.graders import DbFactKept, RefundAmountCorrect

    bad, good = _run("seeded_regression", "C-002", 11), _run("fixed", "C-002", 11)
    kinds = [e["kind"] for e in bad.output["events"]]
    assert kinds.index("model_override") == 2           # 3rd event, right after the investigator
    assert DbFactKept().evaluate(bad).value is False and RefundAmountCorrect().evaluate(bad).value is False
    assert DbFactKept().evaluate(good).value is True and RefundAmountCorrect().evaluate(good).value is True
