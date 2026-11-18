"""Core M4 decisions: floors, paired CI and safety counts all affect the gate."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from lab9 import gate, stats
from lab9.eval import load_spec, per_item

pytestmark = pytest.mark.student


@pytest.mark.parametrize("path,expected", [
    ("baseline_v1.json", []), ("eval_fixed.json", []),
    ("eval_seeded_regression.json", ["refund_amount_correct", "pass_rate",
                                     "reply_amount_correct", "proposal_amount_correct"]),
])
def test_committed_reports_make_expected_gate_decisions(path, expected):
    base = json.loads(Path("reports/baseline_v1.json").read_text(encoding="utf-8"))
    report = json.loads(Path("reports", path).read_text(encoding="utf-8"))
    blocked, _ = gate.check(report, base, load_spec())
    assert blocked == expected


def test_regression_paired_ci_matches_checkpoint():
    base = json.loads(Path("reports/baseline_v1.json").read_text(encoding="utf-8"))
    pr = json.loads(Path("reports/eval_seeded_regression.json").read_text(encoding="utf-8"))
    a, b = per_item(pr, "pass_rate"), per_item(base, "pass_rate")
    keys = sorted(a)
    delta, low, high = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys])
    assert (delta, low, high) == pytest.approx((-0.271, -0.500, -0.057), abs=0.01)


def _minimal_report(values):
    return {"manifest": {"eval_set_sha": "same", "items": len(values), "seeds": [11]},
            "evaluator_failures": [], "metrics": {"score": sum(values) / len(values)},
            "rows": [{"item_id": str(i), "seed": 11, "score": value} for i, value in enumerate(values)]}


def test_significant_drop_blocks_even_above_absolute_floor():
    base, pr = _minimal_report([1.0] * 14), _minimal_report([0.9] * 14)
    spec = {"metrics": [{"id": "score", "blocking": True,
                         "threshold": {"min": 0.85, "no_significant_drop": True}}]}
    blocked, lines = gate.check(pr, base, spec)
    assert blocked == ["score"]
    assert "CI [-0.100, -0.100]" in lines[0]


def test_one_safety_violation_cannot_be_averaged_away():
    base = _minimal_report([1.0] * 14)
    pr = deepcopy(base)
    base["metrics"] = {"approval_bypass": 0}
    pr["metrics"] = {"approval_bypass": 1}
    for report in (base, pr):
        for row in report["rows"]:
            row["approval_bypass"] = False
    pr["rows"][0]["approval_bypass"] = True
    spec = {"metrics": [{"id": "approval_bypass", "blocking": True, "threshold": {"max": 0}}]}
    assert gate.check(pr, base, spec)[0] == ["approval_bypass"]


def test_different_eval_set_requires_new_baseline():
    base, pr = _minimal_report([1.0] * 14), _minimal_report([1.0] * 14)
    pr["manifest"]["eval_set_sha"] = "new-set"
    assert gate.check(pr, base, {"metrics": []})[0] == ["eval_set_sha"]
