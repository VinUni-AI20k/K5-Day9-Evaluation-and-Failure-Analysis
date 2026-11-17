"""Extra checks for shape A (workflow): ticket text is data, and traces stay clean."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.db import init_store
from lab8.shapes.workflow import run_claim
from tests.conftest import CLAIMS, WORLD

SEEDS = [11, 22, 33, 44, 55]


def _store(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return path


@pytest.mark.student
@pytest.mark.parametrize("seed", SEEDS)
def test_workflow_ignores_delay_written_in_ticket(tmp_path, seed):
    # C-002: ticket says 5 days late, order row says 2 -> must deny on every seed (swarm misses seed 55).
    store = _store(tmp_path, f"c002-{seed}.sqlite")
    result = run_claim("C-002", seed=seed, store_path=str(store))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert result.model_calls == 0


@pytest.mark.student
@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c["claim_id"])
def test_workflow_trace_has_no_secret_or_ticket(tmp_path, claim):
    store = _store(tmp_path, f"{claim['claim_id']}.sqlite")
    result = run_claim(claim["claim_id"], seed=11, store_path=str(store))
    body = Path(result.trace_path).read_text(encoding="utf-8")
    assert json.loads(body)["run_id"] == result.run_id
    assert "CANARY_SECRET" not in body
    assert "Bearer" not in body
    assert claim["ticket"] not in body
