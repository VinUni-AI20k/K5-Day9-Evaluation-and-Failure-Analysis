"""Regression test from docs/trace_case.md: seeded_regression C-002@11.

First wrong step: event 3 `model_override` (ticket says 5 days late, DB says 2).
The step-level grader DbFactKept and the ledger grader RefundAmountCorrect must both
fail on the buggy variant and both pass on `fixed` for the same claim@seed.
"""
import pytest

pytestmark = pytest.mark.student


def _grade(shape: str):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9 import graders
    from lab9.trace_case import investigate

    case = investigate(shape, "C-002", 11)
    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=case["label"],
                           output=case["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})
    return case["trial"], graders.DbFactKept().evaluate(ctx).value, graders.RefundAmountCorrect().evaluate(ctx).value


def test_trace_case_c002_seed11_caught_on_regression():
    trial, db_kept, amount_ok = _grade("seeded_regression")
    kinds = [e.get("kind") for e in trial["events"]]
    assert kinds.index("model_override") == 2          # event 3: the first wrong step
    assert db_kept is False and amount_ok is False


def test_trace_case_c002_seed11_clean_on_fixed():
    trial, db_kept, amount_ok = _grade("fixed")
    assert "model_override" not in [e.get("kind") for e in trial["events"]]
    assert db_kept is True and amount_ok is True
