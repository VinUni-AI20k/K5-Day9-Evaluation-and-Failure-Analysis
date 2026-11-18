"""Behavioral checks for the trace case, monetary replies and report integrity."""
import copy
from types import SimpleNamespace

import pytest

from lab9 import gate, stats
from lab9.graders import DbFactKept, ProposalAmountCorrect, RefundAmountCorrect, ReplyAmountCorrect
from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def test_ticket_override_regression_has_fixed_counterexample():
    broken = investigate("seeded_regression", "C-002", 11)
    fixed = investigate("fixed", "C-002", 11)
    event = broken["trial"]["events"][2]
    assert event["kind"] == "model_override" and event["payload"]["delay_days"] == 5
    for case, expected in ((broken, False), (fixed, True)):
        ctx = SimpleNamespace(output=case["trial"], expected_output=case["label"])
        assert DbFactKept().evaluate(ctx).value is expected
        assert RefundAmountCorrect().evaluate(ctx).value is expected


def test_pre_deduction_is_detected_even_when_ledger_stays_zero():
    for shape, expected in (("seeded_regression", False), ("fixed", True)):
        case = investigate(shape, "C-013", 11)
        assert case["trial"]["snapshot"]["refund_vnd"] == 0
        ctx = SimpleNamespace(output=case["trial"], expected_output=case["label"])
        assert ProposalAmountCorrect().evaluate(ctx).value is expected


@pytest.mark.parametrize("text,ledger,want", [
    ("LogiX đã hoàn phí 35.000đ cho đơn O-107 của anh/chị ạ.", 35000, True),
    ("Đã hoàn 35,000 VND.", 20000, False),
    ("Đã hoàn 35 000 đồng.", 35000, True),
    ("Đã hoàn 35000₫ cho đơn O-107.", 20000, False),
    ("Đơn O-35000 trễ 4 ngày, chưa đủ điều kiện hoàn.", 0, True),
    ("Đã hoàn 20.000đ.", 35000, False),
])
def test_reply_amount_uses_money_and_ledger(text, ledger, want):
    ctx = SimpleNamespace(output={"snapshot": {"refund_vnd": ledger},
        "events": [{"kind": "reply", "payload": {"text": text}}]})
    assert ReplyAmountCorrect().evaluate(ctx).value is want


@pytest.mark.parametrize("args", [(0, 0, 1), (5, -1, 1), (5, 6, 1), (5, 1, 6),
                                  (5, 1, 0), (5.0, 1, 1), (True, 1, 1)])
def test_advanced_pass_estimators_reject_invalid_inputs(args):
    for estimator in (stats.pass_at_k, stats.pass_hat_k):
        with pytest.raises(ValueError):
            estimator(*args)


def _clean():
    spec = {"eval_set_version": "v2", "metrics": [
        {"id": "pass_rate", "blocking": True, "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9,
                    "blocking": True, "no_significant_drop": True}]}
    rows = [{"item_id": item, "seed": seed, "pass_rate": True, "slices": ["money_movement"]}
            for item in ("one", "two") for seed in (11, 22)]
    report = {"manifest": {"items": 2, "seeds": [11, 22]}, "rows": rows,
              "metrics": {"pass_rate": 1.0}, "evaluator_failures": []}
    return report, spec


@pytest.mark.parametrize("attack", ["duplicate", "evaluator_error", "retag", "summary", "row_nan", "missing"])
def test_advanced_integrity_rejects_hidden_evidence_changes(attack):
    base, spec = _clean()
    pr = copy.deepcopy(base)
    if attack == "duplicate":
        pr["rows"][-1] = copy.deepcopy(pr["rows"][0])
    elif attack == "evaluator_error":
        pr["evaluator_failures"] = ["grader crashed on an otherwise green run"]
    elif attack == "retag":
        for row in pr["rows"]:
            row["slices"] = []
    elif attack == "summary":
        pr["rows"][0]["pass_rate"] = False
    elif attack == "row_nan":
        pr["rows"][0]["pass_rate"] = float("nan")
    else:
        pr["rows"][0].pop("pass_rate")
    assert gate.integrity_check(pr, base, spec)
    assert gate.integrity_check(base, base, spec, spec) == []


@pytest.mark.parametrize("attack", ["drop_metric", "drop_slice", "nonblocking", "drop_ci", "lower_slice"])
def test_advanced_ratchet_preserves_release_requirements(attack):
    base, spec = _clean()
    loose = copy.deepcopy(spec)
    if attack == "drop_metric":
        loose["metrics"] = []
    elif attack == "drop_slice":
        loose["slices"] = []
    elif attack == "nonblocking":
        loose["metrics"][0]["blocking"] = False
    elif attack == "drop_ci":
        loose["metrics"][0]["threshold"].pop("no_significant_drop")
    else:
        loose["slices"][0]["min"] = 0.5
    assert gate.integrity_check(base, base, loose, spec)
