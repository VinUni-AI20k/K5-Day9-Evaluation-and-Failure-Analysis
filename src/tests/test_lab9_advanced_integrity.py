"""M5-M7 extra self-checks: the trap shapes the checkpoints hint at (duplicate rows, evaluator
failures on a green run, relabelled slices, an edited headline number, a spec ratchet) and the
item-level reliability check. Run: python -m pytest -q -m student -o addopts= -k advanced"""
import copy
import math

import pytest

pytestmark = pytest.mark.student

SEEDS = (1, 2, 3, 4, 5)
ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["money_movement"] if i < 2 else []}
        for i in range(4) for s in SEEDS]
SPEC = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                                               "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9, "blocking": True}],
        "reliability": {"metric": "pass_rate", "max_newly_unreliable_items": 0, "blocking": True}}


def _report(rows, metrics=None):
    rows = copy.deepcopy(rows)
    if metrics is None:
        vals = [r["pass_rate"] for r in rows]
        metrics = {"pass_rate": round(sum(vals) / len(vals), 4)}
    return {"run_id": "t", "manifest": {"eval_set_sha": "x", "items": 4, "seeds": list(SEEDS)},
            "rows": rows, "metrics": metrics, "evaluator_failures": []}


@pytest.fixture(scope="module")
def gate():
    from lab9 import gate
    return gate


def test_clean_report_is_trusted(gate):
    base = _report(ROWS)
    assert gate.integrity_check(base, base, SPEC, SPEC) == []
    assert gate.check(base, base, SPEC, SPEC)[0] == []


def test_duplicated_rows_replacing_failures(gate):
    rows = copy.deepcopy(ROWS)
    rows[3] = dict(rows[2])              # same count, (item, seed) of the failing row replaced by a duplicate
    assert gate.integrity_check(_report(rows), _report(ROWS), SPEC)


def test_evaluator_failures_on_green_run(gate):
    pr = _report(ROWS)
    pr["evaluator_failures"] = ["E-000@1:TrialPass:boom"]
    assert gate.integrity_check(pr, _report(ROWS), SPEC)


def test_row_with_missing_grader_value(gate):
    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = None
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), _report(ROWS), SPEC)


def test_relabelled_slice(gate):
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert gate.integrity_check(_report(rows), _report(ROWS), SPEC)


def test_edited_headline_metric(gate):
    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = False
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), _report(ROWS), SPEC)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "0.9"])
def test_non_numeric_metric(gate, value):
    assert gate.integrity_check(_report(ROWS, {"pass_rate": value}), _report(ROWS), SPEC)


@pytest.mark.parametrize("mutate", [
    lambda s: s["slices"].clear(),
    lambda s: s["slices"][0].update(min=0.5),
    lambda s: s["metrics"][0]["threshold"].pop("no_significant_drop"),
    lambda s: s["metrics"][0].update(blocking=False),
    lambda s: s["metrics"].clear(),
    lambda s: s["reliability"].update(max_newly_unreliable_items=3),
    lambda s: s.pop("reliability"),
    lambda s: s.update(bootstrap={"confidence": 0.999}),
])
def test_ratchet(gate, mutate):
    loose = copy.deepcopy(SPEC)
    mutate(loose)
    assert gate.ratchet_check(loose, SPEC)


def test_stricter_spec_passes_ratchet(gate):
    strict = copy.deepcopy(SPEC)
    strict["metrics"][0]["threshold"]["min"] = 0.9
    strict["slices"][0]["min"] = 0.95
    assert gate.ratchet_check(strict, SPEC) == []


def test_reliability_catches_fix_one_break_another(gate):
    base_rows = copy.deepcopy(ROWS)
    base_rows[5]["pass_rate"] = False                # baseline: E-001 flaky
    pr_rows = copy.deepcopy(ROWS)                    # PR: E-001 fixed, E-003 broken on one seed
    pr_rows[15]["pass_rate"] = False
    base, pr = _report(base_rows), _report(pr_rows)
    assert math.isclose(base["metrics"]["pass_rate"], pr["metrics"]["pass_rate"])
    blocked, _ = gate.reliability_check(pr, base, SPEC)
    assert blocked == ["reliability:pass_rate/newly_unreliable_items"]


def test_reply_amount_parser():
    from lab9.graders import reply_amounts
    ev = [{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-107."}},
          {"kind": "reply", "payload": {"text": "hoàn phí 1.250.000 đồng, mã O-202"}},
          {"kind": "quote", "payload": {"text": "99.000đ"}}]
    assert reply_amounts(ev) == [35000, 1250000]
    other = [{"kind": "reply", "payload": {"text": "Đã hoàn 35k, phần còn lại 1,2 triệu đồng và 20 nghìn đ; 15,000 VND"}}]
    assert reply_amounts(other) == [35000, 1200000, 20000, 15000]
