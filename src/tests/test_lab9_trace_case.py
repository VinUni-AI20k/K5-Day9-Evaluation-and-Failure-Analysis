"""Regression case: ignoring a host denial must stay visible to the outcome grader."""
import pytest

pytestmark = pytest.mark.student


def test_seeded_regression_denial_and_fixed_counterexample():
    from lab9.trace_case import investigate

    broken = investigate("seeded_regression", "C-002", 11)["trial"]
    fixed = investigate("fixed", "C-002", 11)["trial"]
    assert broken["lab8_pass"] is False
    assert broken["result"]["status"] == "resolved"
    assert fixed["lab8_pass"] is True
    assert fixed["result"]["status"] == "denied"
