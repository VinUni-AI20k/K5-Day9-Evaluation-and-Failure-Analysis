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

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    budget = Budget()
    run_id = make_run_id("single", claim_id, seed)
    trace = Trace(run_id)
    state: dict[str, Any] = {}

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        last_tool = seen.get("last_tool")
        if last_tool:
            last_result = seen.get("last_result") or {}
            state[last_tool] = last_result
            trace.add("tool_result", {"tool": last_tool, "result": _sanitize_tool_result(last_tool, last_result)})

        if "get_claim_view" not in state:
            complete(budget, seed=seed, purpose="plan", prompt=f"claim={claim_id}")
            return {"tool": "get_claim_view", "args": {"claim_id": claim_id}}

        claim_view = state["get_claim_view"]
        if not claim_view.get("found"):
            trace.add("decision", {"status": "failed", "reason": "unknown_claim"})
            return {"final": {"status": "failed", "proposal_amount": 0, "error_reason": "unknown_claim"}}

        if not claim_view.get("order_id"):
            complete(budget, seed=seed, purpose="draft", prompt="needs_info")
            trace.add("decision", {"status": "needs_info", "reason": "missing_order_id"})
            return {"final": {"status": "needs_info", "proposal_amount": 0, "error_reason": "missing_order_id"}}

        if "lookup_order" not in state:
            return {
                "tool": "lookup_order",
                "args": {
                    "order_id": claim_view["order_id"],
                    "principal_id": claim_view["principal_id"],
                },
            }

        order_view = state["lookup_order"]
        if not order_view.get("visible"):
            reason = order_view.get("reason")
            complete(budget, seed=seed, purpose="draft", prompt="escalated")
            trace.add("decision", {"status": "escalated", "reason": reason})
            return {"final": {"status": "escalated", "proposal_amount": 0, "error_reason": reason}}

        if "lookup_policy" not in state:
            return {"tool": "lookup_policy", "args": {}}

        if "lookup_refund_history" not in state:
            return {
                "tool": "lookup_refund_history",
                "args": {
                    "order_id": claim_view["order_id"],
                    "principal_id": claim_view["principal_id"],
                },
            }

        if "compute_compensation" not in state:
            return {"tool": "compute_compensation", "args": {"order": order_view["order"]}}

        quote_payload = state["compute_compensation"]
        proposal = int(quote_payload["amount_vnd"])
        complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
        trace.add("quote", safe_dump(quote_payload))
        return {
            "final": {
                "status": "quoted",
                "proposal_amount": proposal,
                "error_reason": quote_payload.get("reason"),
            }
        }

    react_out = run_react(
        conn,
        budget,
        observation={"claim": claim_id},
        decide=decide,
        max_steps=8,
        worker=True,
    )
    final = react_out.get("final") or {}
    if react_out.get("stopped") == "step_cap":
        trace.add("error", {"reason": "step_cap"})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="step_cap",
        )

    final_status = final.get("status")
    if final_status in {"failed", "needs_info", "escalated"}:
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=final_status,
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=final.get("error_reason"),
        )

    proposal = int(final.get("proposal_amount") or 0)
    if proposal <= 0:
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=final.get("error_reason"),
        )

    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    trace.add("host_outcome", {"ok": outcome["ok"], "conflict": outcome.get("conflict"), "reason": outcome.get("reason")})
    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=outcome["reason"],
        )

    return finish(
        conn,
        shape="single",
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )


def _sanitize_tool_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Keep only allowlisted, secret/PII-free fields for the trace."""
    if tool_name == "get_claim_view":
        return {
            "found": bool(result.get("found")),
            "claim_id": result.get("claim_id"),
            "order_id": result.get("order_id"),
        }
    if tool_name == "lookup_policy":
        return {
            "as_of": result.get("as_of"),
            "policy_count": len(result.get("policies") or []),
        }
    return safe_dump(result)
