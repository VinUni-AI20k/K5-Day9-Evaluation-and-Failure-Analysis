"""M2 calibration decisions and undefined statistics must not silently pass."""

from pathlib import Path
import csv
import math

import pytest

from lab9 import stats
from lab9.judge import calibrate

pytestmark = pytest.mark.student


def test_helpful_judge_is_rejected_despite_high_precision():
    result = calibrate(Path("data/eval/judge_helpful_public.csv"))
    assert result["precision"] == 1.0
    assert result["recall"] < 0.7
    assert not result["passed"]


def test_tone_judge_meets_all_floors():
    result = calibrate(Path("data/eval/judge_tone_public.csv"))
    assert result["passed"]
    assert result["corrected_fail_rate"] == pytest.approx(0.3)


@pytest.mark.parametrize("human,judge", [(["PASS"], []), (["UNKNOWN"], ["PASS"])])
def test_invalid_labels_are_not_silently_discarded(human, judge):
    with pytest.raises(ValueError):
        stats.confusion(human, judge)


def test_no_detected_failures_has_zero_precision_and_recall():
    assert stats.precision_recall(["FAIL", "PASS"], ["PASS", "PASS"]) == (0.0, 0.0)


@pytest.mark.parametrize("labels", [[], ["PASS"] * 3, ["FAIL"] * 3])
def test_undefined_kappa_is_rejected(labels):
    with pytest.raises(ValueError):
        stats.cohen_kappa(labels, labels)


def test_complete_disagreement_has_negative_kappa():
    assert stats.cohen_kappa(["PASS", "FAIL"], ["FAIL", "PASS"]) == -1.0


def test_rogan_gladen_upper_clip():
    assert stats.rogan_gladen(1.0, 0.8, 0.9) == 1.0


@pytest.mark.parametrize("observed,sensitivity,specificity", [
    (0.2, 0.5, 0.5), (float("nan"), 0.8, 0.9), (0.2, 1.1, 0.9),
])
def test_rogan_gladen_rejects_undefined_or_invalid_inputs(observed, sensitivity, specificity):
    with pytest.raises(ValueError):
        stats.rogan_gladen(observed, sensitivity, specificity)


def test_constant_judge_fails_calibration_without_crashing(tmp_path):
    path = tmp_path / "constant.csv"
    path.write_text("item_id,reply,human,judge\nX,test,PASS,PASS\n", encoding="utf-8")
    result = calibrate(path)
    assert not result["passed"]
    assert math.isnan(result["kappa"])
    assert math.isnan(result["corrected_fail_rate"])
    assert "correction_error" in result


def test_display_rounding_cannot_make_a_judge_meet_floors(tmp_path):
    path = tmp_path / "borderline.csv"
    human = ["PASS"] * 2500 + ["FAIL"] * 2500
    judge = ["FAIL"] * 501 + ["PASS"] * 1999 + ["PASS"] * 500 + ["FAIL"] * 2000
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["item_id", "reply", "human", "judge"])
        writer.writeheader()
        writer.writerows({"item_id": str(i), "reply": "test", "human": h, "judge": j}
                         for i, (h, j) in enumerate(zip(human, judge)))
    result = calibrate(path)
    # Raw kappa=0.5996 and precision=2000/2501 fall below the floors.
    assert result["kappa"] == 0.6
    assert result["precision"] == 0.8
    assert not result["passed"]
