import json
from pathlib import Path

import pytest

from lab8.durability import InjectedCrash
from lab8.schemas import make_run_id
from lab8.shapes.single import run_claim


def _read_trace(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_single_uses_order_row_for_quote(public_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = run_claim("C-002", seed=55, store_path=str(public_db))

    trace = _read_trace(result.trace_path)
    quote_event = next(event for event in trace["events"] if event["kind"] == "quote")
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert quote_event["payload"]["amount_vnd"] == 0
    assert trace["run_id"] == result.run_id


@pytest.mark.parametrize(
    ("claim_id", "expected_status"),
    [("UNKNOWN-CLAIM", "failed"), ("C-004", "needs_info")],
)
def test_single_early_returns_have_trace(
    public_db, tmp_path, monkeypatch, claim_id, expected_status
):
    monkeypatch.chdir(tmp_path)

    result = run_claim(claim_id, seed=11, store_path=str(public_db))

    trace = _read_trace(result.trace_path)
    assert result.status == expected_status
    assert trace["run_id"] == result.run_id
    assert trace["events"]


def test_single_propagates_crash_after_effect_and_writes_trace(
    public_db, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    run_id = make_run_id("single", "C-001", 11)

    with pytest.raises(InjectedCrash):
        run_claim(
            "C-001",
            seed=11,
            store_path=str(public_db),
            crash_at="after_effect_before_checkpoint",
        )

    trace = _read_trace(str(Path("traces") / f"{run_id}.json"))
    assert trace["run_id"] == run_id
    assert any(event["kind"] == "crash" for event in trace["events"])
