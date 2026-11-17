"""Focused checks for the Shape C security boundary."""

from __future__ import annotations

import json
from pathlib import Path

from lab8.handoff import READONLY_TOOLS
from lab8.shapes.orchestrator import run_claim


def test_orchestrator_handoff_is_read_only_and_trace_is_sanitized(public_db):
    result = run_claim("C-010", seed=11, store_path=str(public_db))
    trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    handoff = next(event["payload"] for event in trace["events"] if event["kind"] == "handoff")
    serialized = json.dumps(trace, ensure_ascii=False)

    assert result.status == "resolved"
    assert set(handoff["allowed_tools"]) <= READONLY_TOOLS
    assert "issue_refund" not in handoff["allowed_tools"]
    assert "CANARY_SECRET_" not in serialized
    assert "parent_secret" not in serialized
    assert "raw_headers" not in serialized
