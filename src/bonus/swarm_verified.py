"""Ablation for the research card (R2, MAST): swarm + one code verifier.

Exactly one variable changes against `lab8.shapes.swarm_reference`: before the
refund is written, a verifier compares the facts the quote used (`delay_days`,
`status`, `damage_verified`) with the structured order row from the read-only
investigator. On a mismatch it re-quotes once from the order row and records a
`verifier_override` event. Peers, model calls, handoff, tools, seeds and prices
are the same as the reference swarm.

    python -m lab8.benchmark --shapes swarm,swarm_verified,workflow \
        --extra-shape swarm_verified=bonus.swarm_verified:run_claim \
        --seeds 11,22,33,44,55 --out reports/ablation_r2.json
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import make_handoff
from lab8.mock_llm import complete, parse_delay_days
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, tool_cost
from lab8.trace import Trace

SHAPE = "swarm_verified"
VERIFIED_FIELDS = ("delay_days", "status", "damage_verified")


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


def verify(proposed_order: dict, structured_order: dict) -> list[str]:
    """Fields where the facts behind the quote disagree with the order row."""
    return [field for field in VERIFIED_FIELDS if proposed_order.get(field) != structured_order.get(field)]


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    budget.add_tool(tool_cost())
    claim_row = conn.execute(
        "SELECT claim_id, principal_id, order_id, ticket FROM claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    if claim_row is None:
        trace.add("error", {"reason": "unknown_claim"})
        return done("failed", 0, "unknown_claim")

    # --- identical to swarm_reference: peers talk, parse the ticket ---------------
    ticket = claim_row["ticket"]
    complete(budget, seed=seed, purpose="peer", prompt=ticket)
    parsed_delay = parse_delay_days(ticket)
    complete(budget, seed=seed, purpose="parse", prompt=ticket)

    if not claim_row["order_id"]:
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        trace.add("decision", {"status": "needs_info"})
        return done("needs_info", 0, "missing_order_id")

    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="check_applicable_policy",
        facts={},
        allowed_tools=["lookup_order", "lookup_policy", "compute_compensation"],
    )
    trace.add("handoff", safe_dump(handoff))
    investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim_row["principal_id"])
    order_view = investigated["tools"].get("lookup_order", {})
    trace.add(
        "investigator",
        {
            "lookup_order": order_view,
            "policy_count": len((investigated["tools"].get("lookup_policy") or {}).get("policies") or []),
        },
    )
    if not order_view.get("visible"):
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return done("escalated", 0, order_view.get("reason"))

    structured = dict(order_view["order"])
    order = dict(structured)
    # Same weakness as the reference: one seed in five trusts the ticket delay.
    if parsed_delay is not None and parsed_delay != int(order["delay_days"]) and seed % 5 == 0:
        order["delay_days"] = parsed_delay
        trace.add("model_override", {"delay_days": parsed_delay})

    quote_payload = investigated["tools"]["compute_compensation"]
    if order["delay_days"] != structured["delay_days"]:
        budget.add_tool(tool_cost())
        quote_payload = compute_compensation(conn, order)

    # --- the one change: code verifier before the write ----------------------------
    mismatched = verify(order, structured)
    if mismatched:
        budget.add_tool(tool_cost())
        quote_payload = compute_compensation(conn, structured)  # max 1 correction round
        trace.add(
            "verifier_override",
            {
                "fields": mismatched,
                "used": {field: structured.get(field) for field in mismatched},
                "requoted_vnd": int(quote_payload["amount_vnd"]),
            },
        )

    proposal = int(quote_payload["amount_vnd"])
    trace.add("quote", safe_dump(quote_payload))
    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
    if proposal <= 0:
        return done("denied", 0, quote_payload.get("reason"))

    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)
