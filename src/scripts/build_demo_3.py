"""Create an offline four-shape walkthrough from fresh public claim runs.

Run from src/: python scripts/build_demo_3.py
The HTML embeds only allowlisted order fields, results, and sanitized traces.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
sys.path.insert(0, str(SRC))

from lab8.app import run_shape
from lab8.db import connect, init_store, load_json, load_jsonl
from lab8.durability import InjectedCrash, committed_audit_count
from lab8.metrics import trial_pass
from lab8.tools import lookup_order


SHAPES = ("workflow", "single", "orchestrator", "swarm")
TEMPLATE = Path(__file__).with_name("demo_3_template.html")
OUTPUT = ROOT / "report" / "team" / "demo_3.html"

SCENARIOS = {
    "T01": "Trễ 4 ngày, đủ điều kiện hoàn ship",
    "T02": "Ticket khai trễ 5 ngày, hồ sơ ghi 2",
    "T03": "Hàng hỏng đã xác minh",
    "T04": "Thiếu mã đơn hàng",
    "T05": "Người yêu cầu không sở hữu đơn",
    "T06": "Ticket viện dẫn chính sách cũ",
    "T07": "Approval đã hết hạn",
    "T08": "Approval thấp hơn quote",
    "T09": "Ticket yêu cầu bỏ qua policy",
    "T10": "Kiểm tra ranh giới dữ liệu riêng",
    "T11": "Gọi lại cùng một claim",
    "T12": "Crash rồi resume",
    "T13": "Đơn đã được hoàn đủ trước đó",
    "T14": "Hoàn bù sau khi xác minh hàng hỏng",
}


def _make_store(path: Path, world: dict, claims: list[dict]) -> None:
    init_store(path, world, claims).close()


def _safety_runs(tmp: Path, world: dict, claims: list[dict]) -> dict:
    result = {}
    for shape in SHAPES:
        retry_store = tmp / f"safety-retry-{shape}.sqlite"
        _make_store(retry_store, world, claims)
        first = run_shape(shape, "C-011", seed=11, store_path=str(retry_store))
        second = run_shape(shape, "C-011", seed=11, store_path=str(retry_store))
        conn = connect(retry_store)
        try:
            retry_rows = conn.execute(
                "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", ("C-011",)
            ).fetchone()["n"]
            retry_audits = committed_audit_count(conn, "C-011")
        finally:
            conn.close()

        crash_store = tmp / f"safety-crash-{shape}.sqlite"
        _make_store(crash_store, world, claims)
        crashed = False
        try:
            run_shape(
                shape, "C-012", seed=11, store_path=str(crash_store),
                crash_at="after_effect_before_checkpoint",
            )
        except InjectedCrash:
            crashed = True
        conn = connect(crash_store)
        try:
            before_rows = conn.execute(
                "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", ("C-012",)
            ).fetchone()["n"]
            before_checkpoint = conn.execute(
                "SELECT COUNT(*) AS n FROM checkpoints WHERE claim_id = ?", ("C-012",)
            ).fetchone()["n"]
        finally:
            conn.close()
        resumed = run_shape(shape, "C-012", seed=11, store_path=str(crash_store))
        conn = connect(crash_store)
        try:
            after_rows = conn.execute(
                "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", ("C-012",)
            ).fetchone()["n"]
            after_audits = committed_audit_count(conn, "C-012")
            after_checkpoint = conn.execute(
                "SELECT COUNT(*) AS n FROM checkpoints WHERE claim_id = ?", ("C-012",)
            ).fetchone()["n"]
        finally:
            conn.close()
        assert first.status == second.status == resumed.status == "resolved"
        assert retry_rows == retry_audits == after_rows == after_audits == 1
        assert crashed and before_rows == 1 and before_checkpoint == 0 and after_checkpoint == 1
        result[shape] = {
            "retry": {"first": first.status, "second": second.status,
                      "ledger_rows": retry_rows, "audits": retry_audits},
            "crash": {"injected": crashed, "before_rows": before_rows,
                      "before_checkpoint": before_checkpoint, "resumed": resumed.status,
                      "after_rows": after_rows, "after_audits": after_audits,
                      "after_checkpoint": after_checkpoint},
        }
    return result


def main() -> None:
    world = load_json(SRC / "data" / "public_world_state.json")
    claims = load_jsonl(SRC / "data" / "public_claims.jsonl")
    benchmark = load_json(SRC / "reports" / "benchmark.json")
    crash = load_json(SRC / "reports" / "crash.json")
    seeds = benchmark["controlled_variables"]["seeds"]
    expected_trials = {
        (row["shape"], row["claim_id"], row["seed"]): row
        for row in benchmark["trials"]
    }
    assert len(claims) == 14 and len(seeds) == 5 and len(expected_trials) == 280
    assert crash["crash_safety"] == "20/20"

    approvals = {row["approval_id"]: row for row in world["approvals"]}
    prior_by_order: dict[str, int] = {}
    for row in world.get("prior_refunds", []):
        prior_by_order[row["order_id"]] = prior_by_order.get(row["order_id"], 0) + row["amount_vnd"]

    runs = []
    with tempfile.TemporaryDirectory(prefix="lab8-demo3-", ignore_cleanup_errors=True) as dirname:
        tmp = Path(dirname)
        for shape in SHAPES:
            for claim in claims:
                for seed in seeds:
                    claim_id = claim["claim_id"]
                    store = tmp / f"{shape}-{claim_id}-{seed}.sqlite"
                    _make_store(store, world, claims)
                    started_at = time.time()
                    result = run_shape(shape, claim_id, seed=seed, store_path=str(store))
                    trace = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
                    conn = connect(store)
                    try:
                        passed, reason = trial_pass(
                            result.as_dict(), claim["expected"], conn, started_at=started_at
                        )
                        order_view = lookup_order(conn, claim.get("order_id"), claim["principal_id"])
                        denials = conn.execute(
                            "SELECT COUNT(*) AS n FROM audit_events "
                            "WHERE claim_id = ? AND event_type = 'policy_denied'",
                            (claim_id,),
                        ).fetchone()["n"]
                    finally:
                        conn.close()
                    benchmark_row = expected_trials[(shape, claim_id, seed)]
                    assert (passed, reason, result.status, len(trace["events"])) == (
                        benchmark_row["passed"], benchmark_row["reason"],
                        benchmark_row["status"], benchmark_row["steps"],
                    ), f"benchmark differs from fresh run: {shape}/{claim_id}/{seed}"
                    approval = approvals.get(claim.get("approval_id"))
                    runs.append({
                        "shape": shape, "claim_id": claim_id, "seed": seed,
                        "passed": passed, "reason": reason,
                        "run_id": result.run_id, "status": result.status,
                        "proposal_amount": result.proposal_amount,
                        "refund_amount": sum(effect["amount_vnd"] for effect in result.refund_effects),
                        "refund_count": len(result.refund_effects),
                        "audit_count": result.committed_audit_count,
                        "policy_denied_count": denials,
                        "model_calls": result.model_calls, "tool_calls": result.tool_calls,
                        "cost_estimate": result.cost_estimate,
                        "trace": trace["events"],
                        "order": order_view.get("order") if order_view["visible"] else None,
                        "order_reason": order_view["reason"],
                        "prior_refunded_vnd": prior_by_order.get(claim.get("order_id"), 0),
                        "approval": ({
                            "approval_id": approval["approval_id"],
                            "approved_vnd": approval["approved_vnd"],
                            "status": approval["status"],
                            "expires_at": approval["expires_at"],
                        } if approval else None),
                    })
        safety = _safety_runs(tmp, world, claims)

    safe_claims = [{
        "claim_id": row["claim_id"], "matrix_id": row["matrix_id"],
        "description": SCENARIOS[row["matrix_id"]],
        "order_id": row.get("order_id"),
        "expected": {key: row["expected"][key] for key in
                     ("status", "proposal_amount", "refund_vnd")},
    } for row in claims]
    code = {
        shape: (SRC / "lab8" / "shapes" / f"{shape if shape != 'swarm' else 'swarm_reference'}.py")
        .read_text(encoding="utf-8")
        for shape in SHAPES
    }
    data = {
        "claims": safe_claims, "runs": runs, "seeds": seeds,
        "metrics": benchmark["by_shape"], "crash_safety": crash["crash_safety"],
        "safety": safety, "code": code,
        "as_of": benchmark["controlled_variables"]["as_of"],
    }
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    forbidden = ["CANARY_SECRET_"]
    for order in world["orders"]:
        forbidden.extend(order[key] for key in ("phone", "address", "internal_note", "item_name"))
    for token in forbidden:
        assert token not in serialized, "sensitive source value would enter demo"
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    OUTPUT.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", serialized), encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(runs)} fresh runs; {crash['crash_safety']} crash suite)")


if __name__ == "__main__":
    main()
