"""M7: adversarial report mutations must fail closed, including on green runs."""
from copy import deepcopy

import pytest

from lab9 import gate
from lab9.eval import aggregate

pytestmark = pytest.mark.student


@pytest.fixture
def spec():
    return {"eval_set_version": "v2", "pass_k": [2], "metrics": [
        {"id": "pass_rate", "blocking": True, "threshold": {"min": 0.85, "no_significant_drop": True}},
        {"id": "approval_bypass", "blocking": True, "threshold": {"max": 0}},
        {"id": "cost_per_success", "blocking": False, "threshold": {"max_increase": 0.1}},
        {"id": "pass_hat_2", "blocking": True, "threshold": {"min": 0.8}}],
        "slices": [{"name": "money", "metric": "pass_rate", "min": 0.9,
                    "blocking": True, "no_significant_drop": True}]}


@pytest.fixture
def report():
    rows = [{"item_id": item, "seed": seed, "pass_rate": True, "approval_bypass": False,
             "cost": 1.0, "slices": ["money", "adversarial"]}
            for item in ("item-a", "item-b") for seed in (11, 22)]
    return {"run_id": "unit", "manifest": {"eval_set_sha": "same", "items": 2, "seeds": [11, 22]},
            "evaluator_failures": [], "rows": rows,
            "metrics": aggregate(rows, ["pass_rate", "approval_bypass"], k_values=[2])}


@pytest.mark.parametrize("kind", [
    "nan", "inf", "negative_inf", "metric_string", "metric_missing", "row_none", "row_missing_grade",
    "row_nan", "duplicate_replacing_row", "duplicate_extra_row", "dropped", "dropped_repaired_manifest",
    "cherry_seeds_repaired_manifest", "changed_item_id", "slice_relabel_all_seeds", "slice_relabel_one_seed",
    "evaluator_failure_on_green", "missing_failures", "duplicate_manifest_seed", "empty_seeds", "wrong_items",
    "wrong_row_seed", "row_string_seed", "invalid_manifest", "invalid_row", "nonfinite_cost",
    "aggregate_forged", "derived_forged", "cost_forged", "slice_string", "seed_bool", "grade_out_of_range",
])
def test_corrupted_reports_block_with_explicit_integrity_reason(spec, report, kind):
    pr = deepcopy(report)
    if kind in ("nan", "inf", "negative_inf", "metric_string"):
        pr["metrics"]["pass_rate"] = {"nan": float("nan"), "inf": float("inf"),
            "negative_inf": -float("inf"), "metric_string": "1.0"}[kind]
    elif kind == "metric_missing":
        del pr["metrics"]["pass_rate"]
    elif kind in ("row_none", "row_nan"):
        pr["rows"][0]["pass_rate"] = None if kind == "row_none" else float("nan")
    elif kind == "row_missing_grade":
        del pr["rows"][0]["pass_rate"]
    elif kind == "grade_out_of_range":
        pr["rows"][0]["pass_rate"] = 2
    elif kind == "duplicate_replacing_row":
        pr["rows"][1] = deepcopy(pr["rows"][0])
    elif kind == "duplicate_extra_row":
        pr["rows"].append(deepcopy(pr["rows"][0]))
    elif kind == "dropped":
        pr["rows"].pop()
    elif kind == "dropped_repaired_manifest":
        pr["rows"] = pr["rows"][:2]
        pr["manifest"]["items"] = 1
    elif kind == "cherry_seeds_repaired_manifest":
        pr["rows"] = [r for r in pr["rows"] if r["seed"] == 11]
        pr["manifest"]["seeds"] = [11]
    elif kind == "changed_item_id":
        for row in pr["rows"]:
            row["item_id"] = row["item_id"].replace("item-a", "replacement")
    elif kind.startswith("slice_relabel"):
        for row in pr["rows"][:(2 if kind.endswith("all_seeds") else 1)]:
            row["slices"] = []
    elif kind == "evaluator_failure_on_green":
        pr["evaluator_failures"] = ["item-a@11:grader:crashed"]
    elif kind == "missing_failures":
        del pr["evaluator_failures"]
    elif kind == "duplicate_manifest_seed":
        pr["manifest"]["seeds"] = [11, 11]
    elif kind == "empty_seeds":
        pr["manifest"]["seeds"] = []
    elif kind == "wrong_items":
        pr["manifest"]["items"] = 9
    elif kind in ("wrong_row_seed", "row_string_seed", "seed_bool"):
        pr["rows"][0]["seed"] = {"wrong_row_seed": 33, "row_string_seed": "11", "seed_bool": True}[kind]
    elif kind == "invalid_manifest":
        pr["manifest"] = []
    elif kind == "invalid_row":
        pr["rows"][0] = None
    elif kind == "nonfinite_cost":
        pr["rows"][0]["cost"] = float("inf")
    elif kind == "aggregate_forged":
        pr["metrics"]["pass_rate"] = 0.9
    elif kind == "derived_forged":
        pr["metrics"]["pass_hat_2"] = 0.9
    elif kind == "cost_forged":
        pr["metrics"]["cost_per_success"] = 0.5
    elif kind == "slice_string":
        pr["rows"][0]["slices"] = "money"
    blocked, lines = gate.check(pr, report, spec, spec)
    assert blocked == ["integrity"]
    assert lines and all("INTEGRITY" in line for line in lines)


@pytest.mark.parametrize("mutation", [
    "lower_min", "raise_max", "raise_max_increase", "remove_threshold", "remove_metric",
    "unblock_metric", "remove_ci", "remove_slice", "lower_slice_min", "unblock_slice",
    "remove_slice_ci", "change_slice_metric", "duplicate_metric", "duplicate_slice",
    "nan_threshold", "invalid_blocking",
])
def test_spec_relaxations_cannot_be_hidden_by_green_reports(spec, report, mutation):
    loose = deepcopy(spec)
    metric, slice_entry = loose["metrics"][0], loose["slices"][0]
    if mutation == "lower_min":
        metric["threshold"]["min"] = 0.5
    elif mutation == "raise_max":
        loose["metrics"][1]["threshold"]["max"] = 1
    elif mutation == "raise_max_increase":
        loose["metrics"][2]["threshold"]["max_increase"] = 0.2
    elif mutation == "remove_threshold":
        del metric["threshold"]["min"]
    elif mutation == "remove_metric":
        loose["metrics"].pop(2)  # Even removing a warning is a ratchet violation.
    elif mutation == "unblock_metric":
        metric["blocking"] = False
    elif mutation == "remove_ci":
        del metric["threshold"]["no_significant_drop"]
    elif mutation == "remove_slice":
        loose["slices"] = []
    elif mutation == "lower_slice_min":
        slice_entry["min"] = 0.5
    elif mutation == "unblock_slice":
        slice_entry["blocking"] = False
    elif mutation == "remove_slice_ci":
        slice_entry["no_significant_drop"] = False
    elif mutation == "change_slice_metric":
        slice_entry["metric"] = "approval_bypass"
    elif mutation == "duplicate_metric":
        loose["metrics"].append(deepcopy(metric))
    elif mutation == "duplicate_slice":
        loose["slices"].append(deepcopy(slice_entry))
    elif mutation == "nan_threshold":
        metric["threshold"]["min"] = float("nan")
    elif mutation == "invalid_blocking":
        metric["blocking"] = "false"
    assert gate.check(report, report, loose, spec)[0] == ["integrity"]


def test_self_comparison_and_reordering_are_not_false_alarms(spec, report):
    pr = deepcopy(report)
    pr["rows"].reverse()
    pr["manifest"]["seeds"].reverse()
    for row in pr["rows"]:
        row["slices"].reverse()
    assert gate.integrity_check(pr, report, spec, spec) == []
    assert gate.check(pr, report, spec, spec)[0] == []


def test_stricter_policy_and_added_metrics_are_allowed(spec, report):
    stricter = deepcopy(spec)
    stricter["metrics"][0]["threshold"]["min"] = 0.95
    stricter["metrics"][2]["blocking"] = True
    stricter["metrics"][2]["threshold"]["max_increase"] = 0.05
    stricter["metrics"].append({"id": "pass_at_2", "blocking": True, "threshold": {"min": 0.9}})
    stricter["slices"][0]["min"] = 0.95
    assert gate.integrity_check(report, report, stricter, spec) == []
    assert gate.check(report, report, stricter, spec)[0] == []


def test_ratchet_resets_only_when_eval_set_version_changes(spec, report):
    revised = deepcopy(spec)
    revised["eval_set_version"] = "v3"
    revised["metrics"][0]["threshold"]["min"] = 0.5
    assert gate.integrity_check(report, report, revised, spec) == []
    revised["eval_set_version"] = "v2"
    revised["metric_spec_version"] = "999"
    assert any("ratchet" in p for p in gate.integrity_check(report, report, revised, spec))


def test_corrupt_baseline_also_blocks(spec, report):
    broken_base = deepcopy(report)
    broken_base["evaluator_failures"] = ["failed"]
    assert gate.check(report, broken_base, spec)[0] == ["integrity"]


def test_removing_eval_version_cannot_disable_ratchet(spec, report):
    loose = deepcopy(spec)
    del loose["eval_set_version"]
    loose["metrics"][0]["threshold"]["min"] = 0.1
    assert any("ratchet" in p for p in gate.integrity_check(report, report, loose, spec))


def test_new_eval_version_can_remove_old_metric_after_rebaselining(spec, report):
    new_spec = deepcopy(spec)
    new_spec["eval_set_version"] = "v3"
    new_spec["metrics"] = [m for m in new_spec["metrics"] if m["id"] != "approval_bypass"]
    fresh = deepcopy(report)
    fresh["manifest"]["eval_set_sha"] = "new-dataset"
    del fresh["metrics"]["approval_bypass"]
    for row in fresh["rows"]:
        del row["approval_bypass"]
    assert gate.integrity_check(fresh, fresh, new_spec, spec) == []


def test_seeds_in_report_must_match_policy_when_declared(spec, report):
    spec["seeds"] = [33, 44]
    assert gate.check(report, report, spec)[0] == ["integrity"]


def test_cli_malformed_manifest_is_an_explicit_integrity_block(spec, report, tmp_path, capsys):
    import json
    import yaml

    bad = deepcopy(report)
    bad["manifest"] = None
    pr, base, policy = tmp_path / "pr.json", tmp_path / "base.json", tmp_path / "spec.yaml"
    pr.write_text(json.dumps(bad), encoding="utf-8")
    base.write_text(json.dumps(report), encoding="utf-8")
    policy.write_text(yaml.safe_dump(spec), encoding="utf-8")
    assert gate.main(["--pr", str(pr), "--baseline", str(base), "--spec", str(policy)]) == 1
    assert "INTEGRITY" in capsys.readouterr().out
