"""Regression for docs/trace_case.md: seeded_regression C-002@11 (FM-03, first wrong step = event #3)."""

import pytest

from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def _case(shape: str):
    case = investigate(shape, "C-002", 11)
    return case["trial"], case["label"]


def test_seeded_regression_overrides_db_fact():
    trial, label = _case("seeded_regression")
    kinds = [e.get("kind") for e in trial["events"]]
    assert kinds[2] == "model_override"                              # event #3
    assert trial["snapshot"]["refund_vnd"] != label["refund_vnd"]    # wrong money in the ledger


def test_fixed_keeps_db_fact():
    trial, label = _case("fixed")
    assert "model_override" not in [e.get("kind") for e in trial["events"]]
    assert trial["snapshot"]["refund_vnd"] == label["refund_vnd"] == 0
