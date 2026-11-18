"""Regression test from docs/trace_case.md: C-002@11, ticket says 5 days late, DB says 2 (FM-03).

The first wrong step is the `model_override` event that replaces the DB's delay_days with the
ticket's. The test runs the real shape on a fresh store (MockLLM, deterministic) and checks
the step-level and ledger-level graders: they must fire on the buggy variant and stay quiet on `fixed`.
"""
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.student
CLAIM, SEED = "C-002", 11


def _trial(shape, tmp_path):
    from lab9 import variants
    from lab9.eval import load_spec, load_world, make_task

    variants.register()
    spec = load_spec()
    world, claims = load_world(spec)
    labels = json.loads(Path(spec["labels"]).read_text(encoding="utf-8"))
    return make_task(shape, world, claims, labels, tmp_path)({"claim_id": CLAIM, "seed": SEED}), labels[CLAIM]


def _ctx(trial, label):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_trace_case_c002_first_wrong_step_is_model_override(tmp_path):
    from lab9 import graders

    trial, label = _trial("seeded_regression", tmp_path)
    kinds = [e["kind"] for e in trial["events"]]
    assert "model_override" in kinds, kinds
    first_bad = kinds.index("model_override")
    assert kinds[first_bad - 1] == "investigator"           # DB was read correctly just before
    assert trial["events"][first_bad]["payload"]["delay_days"] == 5
    ctx = _ctx(trial, label)
    assert graders.DbFactKept().evaluate(ctx).value is False
    assert graders.RefundAmountCorrect().evaluate(ctx).value is False   # ledger 20000, label 0


def test_trace_case_c002_fixed_keeps_db_fact(tmp_path):
    from lab9 import graders

    trial, label = _trial("fixed", tmp_path)
    assert "model_override" not in [e["kind"] for e in trial["events"]]
    ctx = _ctx(trial, label)
    assert graders.DbFactKept().evaluate(ctx).value is True
    assert graders.RefundAmountCorrect().evaluate(ctx).value is True
    assert graders.ReplyMatchesLedger().evaluate(ctx).value is True
