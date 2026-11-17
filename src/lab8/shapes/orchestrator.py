"""Shape C — orchestrator plus read-only investigator.

Luồng:
1. Orchestrator đọc claim bằng get_claim_view (không SELECT *), không gửi ticket cho investigator.
2. Thiếu order_id -> needs_info (không ghi ledger).
3. Handoff = make_handoff (allowlist trong code). facts chỉ chứa các key an toàn.
   Investigator chỉ có tool đọc: lookup_order, lookup_policy, lookup_refund_history, compute_compensation.
4. Orchestrator lấy quote từ order row (bỏ qua số ngày trong ticket), rồi là bên duy nhất gọi
   durability.issue_refund với QUOTE ĐẦY ĐỦ (host tự trừ số đã hoàn của đơn).
5. Trace chỉ ghi handoff đã sanitize và kết quả đã lọc, không ghi ticket/parent context.
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import HandoffError, make_handoff
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"
INVESTIGATOR_TOOLS = [
    "lookup_order",
    "lookup_policy",
    "lookup_refund_history",
    "compute_compensation",
]


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


def _fail(conn, claim_id, seed, budget, trace, reason, proposal=0, status="failed") -> RunResult:
    trace.add("error", {"reason": reason})
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


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    run_id = make_run_id(SHAPE, claim_id, seed)
    trace = Trace(run_id)
    try:
        return _orchestrate(conn, claim_id, seed, crash_at, budget, trace)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    except (HandoffError, ToolRejected) as exc:
        return _fail(conn, claim_id, seed, budget, trace, f"handoff_rejected:{type(exc).__name__}")
    except Exception as exc:  # run_claim không được raise
        return _fail(conn, claim_id, seed, budget, trace, f"unexpected:{type(exc).__name__}")


def _orchestrate(conn, claim_id, seed, crash_at, budget: Budget, trace: Trace) -> RunResult:
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim.get("found"):
        return _fail(conn, claim_id, seed, budget, trace, "unknown_claim")

    # Một lần gọi model để đọc ticket. Kết quả KHÔNG dùng để quyết định số tiền.
    complete(budget, seed=seed, purpose="peer", prompt=claim["ticket"])

    if not claim.get("order_id"):
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        trace.add("decision", {"status": "needs_info"})
        return finish(
            conn, shape=SHAPE, claim_id=claim_id, seed=seed, status="needs_info",
            proposal_amount=0, budget=budget, trace=trace, error_reason="missing_order_id",
        )

    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="investigate_order_and_quote",
        facts={},
        allowed_tools=INVESTIGATOR_TOOLS,
    )
    trace.add("handoff", safe_dump(handoff))

    found = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
    tools = found["tools"]
    order_view = tools.get("lookup_order") or {}
    history = tools.get("lookup_refund_history") or {}
    trace.add(
        "investigator",
        {
            "order_visible": bool(order_view.get("visible")),
            "order_reason": order_view.get("reason"),
            "order": order_view.get("order"),
            "refund_count": history.get("refund_count"),
            "refunded_vnd": history.get("refunded_vnd"),
        },
    )

    if not order_view.get("visible"):
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return finish(
            conn, shape=SHAPE, claim_id=claim_id, seed=seed, status="escalated",
            proposal_amount=0, budget=budget, trace=trace, error_reason=order_view.get("reason"),
        )

    quote_payload = tools.get("compute_compensation")
    if not quote_payload:
        return _fail(conn, claim_id, seed, budget, trace, "no_quote")
    proposal = int(quote_payload["amount_vnd"])
    trace.add("quote", {k: quote_payload.get(k) for k in ("amount_vnd", "reason", "clause_ids")})
    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")

    if proposal <= 0:
        return finish(
            conn, shape=SHAPE, claim_id=claim_id, seed=seed, status="denied",
            proposal_amount=0, budget=budget, trace=trace, error_reason=quote_payload.get("reason"),
        )

    outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("host", {"ok": outcome["ok"], "reason": outcome.get("reason")})
    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return finish(
            conn, shape=SHAPE, claim_id=claim_id, seed=seed, status=status,
            proposal_amount=proposal, budget=budget, trace=trace, error_reason=outcome["reason"],
        )
    return finish(
        conn, shape=SHAPE, claim_id=claim_id, seed=seed, status="resolved",
        proposal_amount=proposal, budget=budget, trace=trace, error_reason=None,
    )
