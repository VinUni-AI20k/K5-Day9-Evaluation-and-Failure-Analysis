"""Regression test for docs/trace_case.md (FM-03 ticket_trust).

Trial: swarm C-002@55 in reports/baseline_v1.json. First wrong step: event 3 `model_override`
{"delay_days": 5} right after event 2 read delay_days = 2 from the DB. The test pins that step
and the graders that must catch it, on the variant that still has the bug and on `fixed`."""
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.student


@pytest.fixture(autouse=True)
def _restore_shapes():
    """lab9.variants.register() adds shapes to lab8.shapes.SHAPES; keep Lab 8's registry clean."""
    from lab8.shapes import SHAPES
    saved = dict(SHAPES)
    yield
    SHAPES.clear()
    SHAPES.update(saved)


def _trial(shape: str, claim: str, seed: int):
    from lab9.trace_case import investigate
    case = investigate(shape, claim, seed)
    return case["trial"], case["label"]


def _grade(name: str, trial, label) -> bool:
    from lab9.graders import GRADERS
    return bool(GRADERS[name]().evaluate(SimpleNamespace(output=trial, expected_output=label)).value)


@pytest.mark.parametrize("shape,seed", [("swarm", 55), ("seeded_regression", 11)])
def test_lab9_trace_case_ticket_trust_is_caught(shape, seed):
    trial, label = _trial(shape, "C-002", seed)
    kinds = [e["kind"] for e in trial["events"]]
    first_bad = kinds.index("model_override")
    db_delay = trial["events"][first_bad - 1]["payload"]["lookup_order"]["order"]["delay_days"]
    assert kinds[first_bad - 1] == "investigator" and db_delay == 2
    assert trial["events"][first_bad]["payload"] == {"delay_days": 5}
    assert not _grade("db_fact_kept", trial, label)          # step level: the override event
    assert not _grade("refund_amount_correct", trial, label)  # outcome level: 20.000đ in the ledger, label 0
    assert trial["snapshot"]["refund_vnd"] == 20000 and label["refund_vnd"] == 0


@pytest.mark.parametrize("seed", [11, 55])
def test_lab9_trace_case_fixed_keeps_db_fact(seed):
    trial, label = _trial("fixed", "C-002", seed)
    assert "model_override" not in [e["kind"] for e in trial["events"]]
    assert _grade("db_fact_kept", trial, label)
    assert _grade("refund_amount_correct", trial, label)
    assert trial["result"]["status"] == "denied"
