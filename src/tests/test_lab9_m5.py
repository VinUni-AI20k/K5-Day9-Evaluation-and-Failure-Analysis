"""M5: slice decisions must follow item outcomes, not aggregate metrics/names."""

from copy import deepcopy

import pytest

from lab9 import gate

pytestmark = pytest.mark.student


def report(values, *, name="money_movement", outside=()):
    rows = [{"item_id": f"I-{i}", "seed": seed, "pass_rate": value, "slices": [name]}
            for i, outcomes in enumerate(values) for seed, value in enumerate(outcomes)]
    rows += [{"item_id": f"O-{i}", "seed": seed, "pass_rate": value, "slices": []}
             for i, value in enumerate(outside) for seed in range(len(values[0]))]
    return {"manifest": {"eval_set_sha": "same", "items": len(values) + len(outside),
                         "seeds": sorted({r['seed'] for r in rows})},
            "rows": rows, "evaluator_failures": [],
            "metrics": {"pass_rate": round(sum(r["pass_rate"] for r in rows) / len(rows), 4)}}


def spec(**kwargs):
    entry = {"name": "money_movement", "metric": "pass_rate", "min": 0.9, "blocking": True, **kwargs}
    return {"metrics": [{"id": "pass_rate", "blocking": True, "threshold": {"min": 0.85}}],
            "slices": [entry]}


def test_small_slice_regression_is_not_hidden_by_overall_average():
    base = report([[True] * 5, [True] * 5], outside=[True] * 100)
    pr = report([[False] * 5, [True] * 5], outside=[True] * 100)
    assert pr["metrics"]["pass_rate"] > 0.85
    assert gate.check(pr, base, {**spec(), "slices": []})[0] == []
    assert gate.check(pr, base, spec())[0] == ["slice:money_movement/pass_rate"]


def test_slice_average_weights_items_equally_not_seed_rows():
    base = report([[True] * 9, [True]])
    pr = report([[True] * 9, [False]])
    # Row average=0.9, but the item average is 0.5 and must fail min=0.8.
    blocked, lines = gate.slice_check(pr, base, spec(min=0.8))
    assert blocked == ["slice:money_movement/pass_rate"]
    assert "0.5000" in lines[0]


def test_significant_slice_drop_blocks_even_above_floor():
    base = report([[1.0], [1.0], [1.0], [1.0]])
    pr = report([[0.9], [0.9], [0.9], [0.9]])
    assert gate.slice_check(pr, base, spec(min=0.85, no_significant_drop=True))[0]


def test_identical_slice_passes_and_row_order_does_not_change_pairing():
    base = report([[True, False], [True, True], [True, True]])
    pr = deepcopy(base)
    pr["rows"].reverse()
    assert gate.slice_check(pr, base, spec(min=0.8, no_significant_drop=True))[0] == []


def test_nonblocking_slice_warns_without_blocking():
    base, pr = report([[True], [True]]), report([[False], [True]])
    blocked, lines = gate.slice_check(pr, base, spec(blocking=False))
    assert blocked == []
    assert lines[0].endswith("warn")


def test_single_item_identical_slice_has_zero_difference():
    base = report([[True, True]])
    blocked, lines = gate.slice_check(deepcopy(base), base, spec(no_significant_drop=True))
    assert blocked == []
    assert "CI [+0.000, +0.000]" in lines[0]


@pytest.mark.parametrize("kind", ["empty", "missing_metric", "changed_items", "nan"])
def test_unscorable_blocking_slice_cannot_pass(kind):
    base, pr = report([[True], [True]]), report([[True], [True]])
    if kind == "empty":
        for row in pr["rows"]:
            row["slices"] = []
    elif kind == "missing_metric":
        for row in pr["rows"]:
            del row["pass_rate"]
    elif kind == "changed_items":
        pr["rows"][0]["item_id"] = "different"
    else:
        pr["rows"][0]["pass_rate"] = float("nan")
    blocked, lines = gate.slice_check(pr, base, spec())
    assert blocked == ["slice:money_movement/pass_rate"]
    assert "MISSING" in lines[0]


def test_slice_minimum_uses_unrounded_value():
    base, pr = report([[1.0], [1.0]]), report([[0.89999], [0.89999]])
    assert gate.slice_check(pr, base, spec())[0]


def test_arbitrary_slice_and_metric_names_are_supported():
    base, pr = report([[True], [True]], name="custom"), report([[False], [True]], name="custom")
    for r in (base, pr):
        for row in r["rows"]:
            row["quality"] = row.pop("pass_rate")
    s = {"slices": [{"name": "custom", "metric": "quality", "min": 0.9, "blocking": True}]}
    assert gate.slice_check(pr, base, s)[0] == ["slice:custom/quality"]
