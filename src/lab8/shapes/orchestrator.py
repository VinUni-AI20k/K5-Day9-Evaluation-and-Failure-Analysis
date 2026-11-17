"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import json
from typing import Any

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.handoff import make_handoff
from lab8.mock_llm import complete
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    return _run_claim(
        claim_id, seed=seed, store_path=store_path, crash_at=crash_at,
        shape="orchestrator", draft_reply=True,
    )


def run_claim_no_draft(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Research-card ablation: disable only the final draft model call.

    Register via --extra-shape; the four official shapes remain unchanged.
    This measures scored task behaviour, not customer-facing reply quality.
    """
    return _run_claim(
        claim_id, seed=seed, store_path=store_path, crash_at=crash_at,
        shape="orchestrator_no_draft", draft_reply=False,
    )


def _run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None,
    shape: str,
    draft_reply: bool,
) -> RunResult:
    conn = connect(store_path)
    budget = Budget()
    trace = Trace(make_run_id(shape, claim_id, seed))

    def model(purpose: str, payload: dict[str, Any]) -> None:
        # MockLLM mô phỏng từng vai; chữ trả về không được dùng làm lệnh ghi.
        complete(budget, seed=seed, purpose=purpose, prompt=json.dumps(payload, ensure_ascii=False))
        trace.add("model_call", {"purpose": purpose})

    def done(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
        if draft_reply:
            model("draft", {"status": status, "proposal_amount": proposal})
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    try:
        budget.add_tool(tool_cost())
        claim = get_claim_view(conn, claim_id)
        trace.add("claim_lookup", {"found": claim["found"]})
        if not claim["found"]:
            return done("failed", reason="unknown_claim")
        if not claim["order_id"]:
            return done("needs_info", reason="missing_order_id")

        # 1. Orchestrator giao việc qua handoff allowlist, không gửi ticket/context.
        handoff = make_handoff(
            request_id=f"REQ-{claim_id}",
            claim_id=claim_id,
            task="check_applicable_policy",
            facts={},
            allowed_tools=["lookup_order", "lookup_policy"],
        )
        model("plan", handoff)
        trace.add("handoff", handoff)

        # 2. Investigator chỉ dùng tool đọc và tra đơn trong scope của chủ claim.
        investigated = run_readonly_investigators(
            conn, budget, handoff, principal_id=claim["principal_id"]
        )
        order_view = investigated["tools"]["lookup_order"]
        evidence = {
            "lookup_order": order_view,
            "policy_count": len(investigated["tools"]["lookup_policy"]["policies"]),
        }
        model("investigate", {"task": handoff["task"], "evidence": evidence})
        trace.add("investigator_result", evidence)
        if not order_view["visible"]:
            return done("escalated", reason=order_view["reason"])

        # 3. Orchestrator tính quote bằng code từ order view đã lọc.
        budget.add_tool(tool_cost())
        quote = compute_compensation(conn, order_view["order"])
        trace.add("quote", quote)
        proposal = int(quote["amount_vnd"])
        if proposal <= 0:
            return done("denied", reason=quote["reason"])

        # 4. Chỉ orchestrator gọi host, truyền nguyên quote và điểm crash.
        trace.add("refund_requested", {"proposal_amount": proposal})
        trace.write()
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
        trace.add("refund_result", {"ok": outcome["ok"], "reason": outcome["reason"]})
        if not outcome["ok"]:
            status = "failed" if outcome["conflict"] else "denied"
            return done(status, proposal, outcome["reason"])
        return done("resolved", proposal)
    finally:
        # InjectedCrash phải truyền ra ngoài để test mô phỏng crash/resume thật.
        conn.close()
