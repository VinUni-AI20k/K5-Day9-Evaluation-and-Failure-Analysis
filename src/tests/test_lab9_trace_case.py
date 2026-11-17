"""Regression case for C-002: ticket data must not override the database."""

import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9.graders import DbFactKept, RefundAmountCorrect
from lab9.trace_case import investigate


@pytest.mark.student
@pytest.mark.parametrize("shape, expected", [("seeded_regression", False), ("fixed", True)])
def test_lab9_c002_ticket_does_not_override_db(shape, expected):
    case = investigate(shape, "C-002", 11)
    ctx = EvaluatorContext(name="C-002@11", inputs={}, metadata=None,
                           expected_output=case["label"], output=case["trial"],
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    assert DbFactKept().evaluate(ctx).value is expected
    assert RefundAmountCorrect().evaluate(ctx).value is expected
