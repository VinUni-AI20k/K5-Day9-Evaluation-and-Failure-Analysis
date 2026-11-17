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

from typing import Any

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import compute_compensation, tool_cost
from lab8.trace import Trace


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

    def finish_run(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
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
        last_tool = observation.get("last_tool")
        complete(budget, seed=seed, purpose="react", prompt=f"Review {last_tool or 'start'}")
        if last_tool is None:
            return {"tool": "get_claim_view", "args": {"claim_id": claim_id}}

        trace.add("read", {"tool": last_tool})
        if last_tool == "get_claim_view":
            claim = observation["last_result"]
            if claim["found"] and claim.get("order_id"):
                return {
                    "tool": "lookup_order",
                    "args": {
                        "order_id": claim["order_id"],
                        "principal_id": claim["principal_id"],
                    },
                }
        return {"final": {}}

    try:
        try:
            result = run_react(conn, budget, observation={}, decide=decide, max_steps=8, worker=True)
        except ToolRejected:
            return finish_run("failed", reason="tool_rejected")

        if result["stopped"] == "step_cap":
            return finish_run("failed", reason="step_cap")

        last = result["observation"]
        data = last["last_result"]
        if last["last_tool"] == "get_claim_view":
            if not data["found"]:
                return finish_run("failed", reason="unknown_claim")
            return finish_run("needs_info", reason="missing_order_id")
        if not data["visible"]:
            return finish_run("escalated", reason=data["reason"])

        budget.add_tool(tool_cost())
        quote = compute_compensation(conn, data["order"])
        proposal = quote["amount_vnd"]
        trace.add("quote", {"amount_vnd": proposal, "reason": quote["reason"]})
        if proposal == 0:
            return finish_run("denied", reason=quote["reason"])

        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
        if outcome["ok"]:
            return finish_run("resolved", proposal)
        status = "failed" if outcome["conflict"] else "denied"
        return finish_run(status, proposal, outcome["reason"])
    finally:
        conn.close()
