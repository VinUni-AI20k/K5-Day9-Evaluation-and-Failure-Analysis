"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import json
from typing import Any

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace


def _read_action(facts: dict[str, Any]) -> dict[str, Any]:
    """Adapt observations to read actions; MockLLM has no structured tool output.

    The mock supplies planning text and token usage. This adapter implements the
    action policy in code for the offline lab, rather than pretending that its
    text is a real model-selected function call. No action can write money.
    """
    if "get_claim_view" not in facts:
        return {"tool": "get_claim_view", "args": {"claim_id": facts["claim_id"]}}

    claim = facts["get_claim_view"]
    if not claim["found"] or not claim["order_id"]:
        return {"final": {}}
    if "lookup_order" not in facts:
        return {
            "tool": "lookup_order",
            "args": {"order_id": claim["order_id"], "principal_id": claim["principal_id"]},
        }

    order_view = facts["lookup_order"]
    if not order_view["visible"]:
        return {"final": {}}
    if "compute_compensation" not in facts:
        return {"tool": "compute_compensation", "args": {"order": order_view["order"]}}
    return {"final": {}}


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    budget = Budget()
    trace = Trace(make_run_id("single", claim_id, seed))
    facts: dict[str, Any] = {"claim_id": claim_id}
    step = 0

    def done(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    def decide(observation: dict[str, Any]) -> dict[str, Any]:
        nonlocal step
        last_tool = observation.get("last_tool")
        if last_tool:
            result = observation["last_result"]
            if last_tool == "get_claim_view":
                # Ticket có thể chứa injection/PII: không đưa vào prompt hoặc trace.
                result = {
                    key: result[key]
                    for key in ("found", "claim_id", "order_id", "principal_id")
                    if key in result
                }
            facts[last_tool] = result
            trace.add("tool_result", {"tool": last_tool, "result": result})

        # MockLLM không sinh function call. Adapter chọn action từ dữ kiện tool;
        # lời model trả về không được dùng làm số tiền, approval hay lệnh ghi.
        step += 1
        complete(budget, seed=seed, purpose="plan", prompt=json.dumps(facts, ensure_ascii=False))
        action = _read_action(facts)
        trace.add("react_step", {"step": step, "action": action.get("tool", "final")})
        return action

    try:
        # Runtime chặn tool ghi, áp dụng tối đa 8 vòng observe -> decide -> read.
        loop = run_react(
            conn,
            budget,
            observation={"claim_id": claim_id},
            decide=decide,
            max_steps=8,
            worker=True,
        )
        if loop["stopped"] != "final":
            return done("failed", reason="step_cap")

        # Code kiểm dữ kiện đã đọc, không tin status/số tiền do model đề xuất.
        claim = facts["get_claim_view"]
        if not claim["found"]:
            return done("failed", reason="unknown_claim")
        if not claim["order_id"]:
            return done("needs_info", reason="missing_order_id")
        order_view = facts["lookup_order"]
        if not order_view["visible"]:
            return done("escalated", reason=order_view["reason"])

        quote = facts["compute_compensation"]
        proposal = int(quote["amount_vnd"])
        if proposal <= 0:
            return done("denied", reason=quote["reason"])

        # Vòng agent đã kết thúc. Chỉ code ở đây mới gọi cửa ghi của host.
        trace.add("refund_requested", {"proposal_amount": proposal})
        trace.write()
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
        trace.add("refund_result", {"ok": outcome["ok"], "reason": outcome["reason"]})
        if not outcome["ok"]:
            status = "failed" if outcome["conflict"] else "denied"
            return done(status, proposal, outcome["reason"])
        return done("resolved", proposal)
    finally:
        # Không bắt InjectedCrash: test phải quan sát được crash thật.
        conn.close()
