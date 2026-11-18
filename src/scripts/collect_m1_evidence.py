"""Replay M1 evidence without changing Lab 8 or the supplied variants.

Run from src/: python -m scripts.collect_m1_evidence
Reports are generated from fresh SQLite stores, never entered by hand.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lab8.console import utf8_stdio
from lab8.db import load_json, load_jsonl
from lab8.shapes import SHAPES
from lab9 import variants
from lab9.eval import WORLD, make_task
from lab9.variant_agent import make_shape


# One bug at a time isolates the cause; all other behavior uses the fixed DB rule.
PROBES = (
    ("FM-01", "leaky_trace", "C-010"),
    ("FM-02", "ignore_denied", "C-007"),
    ("FM-03", "ticket_trust", "C-002"),
    ("FM-04", "sum_parts", "C-014"),
    ("FM-04", "round_down", "C-001"),
    ("FM-05", "pre_deducted", "C-014"),
    ("FM-06", "stale_clause", "C-006"),
    ("FM-07", "sibling_refund", "C-001"),
    ("FM-08", "misreport", "C-008"),
)


def summarize(trial: dict) -> dict:
    return {k: trial[k] for k in (
        "result", "events", "snapshot", "unexpected_rows", "lab8_pass", "lab8_reason"
    )}


def main() -> int:
    utf8_stdio()
    variants.register()
    world = load_json(WORLD)
    claims = load_jsonl(Path("data/public_claims.jsonl"))
    labels = {c["claim_id"]: c["expected"] for c in claims}
    sources = (WORLD, Path("data/public_claims.jsonl"),
               Path("lab8/shapes/swarm_reference.py"), Path("lab9/variant_agent.py"))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    now = datetime.now(timezone(timedelta(hours=7)))
    report = {
        "run_id": f"M1-{now:%Y%m%d}-" + hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest()[:12],
        "manifest": {"generated_at": now.isoformat(), "backend": "MockLLM",
                     "items": len(claims), "seeds": [11, 22, 33, 44, 55],
                     "source_sha256": hashes, "isolation": "fresh_sqlite_per_trial"},
        "reference": [], "probes": [], "seeded_anchor": {},
    }
    with tempfile.TemporaryDirectory(prefix="lab9-m1-", ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)

        def run(shape, claim_id, seed):
            with tempfile.TemporaryDirectory(dir=root, ignore_cleanup_errors=True) as case:
                return summarize(make_task(shape, world, claims, labels, Path(case))(
                    {"claim_id": claim_id, "seed": seed}
                ))

        for claim in claims:
            for seed in report["manifest"]["seeds"]:
                trial = run("swarm", claim["claim_id"], seed)
                report["reference"].append({"claim_id": claim["claim_id"], "seed": seed, **trial})
        for fm, bug, claim_id in PROBES:
            shape = f"m1_{bug}"
            SHAPES[shape] = make_shape(shape, {"no_override", bug})
            report["probes"].append({
                "failure_mode": fm, "bug": bug, "claim_id": claim_id, "seed": 11,
                "label": labels[claim_id], "trial": run(shape, claim_id, 11),
                "fixed": run("fixed", claim_id, 11),
            })
        report["seeded_anchor"] = {
            "claim_id": "C-002", "seed": 11, "label": labels["C-002"],
            "trial": run("seeded_regression", "C-002", 11),
            "fixed": run("fixed", "C-002", 11),
        }
    path = Path("reports/m1_trace_evidence.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [f"{r['claim_id']}@{r['seed']}" for r in report["reference"] if not r["lab8_pass"]]
    print(f"{report['run_id']}: reference {len(report['reference'])} trials; failures={failed}")
    for probe in report["probes"]:
        trial = probe["trial"]
        print(f"{probe['failure_mode']} {probe['bug']} {probe['claim_id']}@11 "
              f"lab8={trial['lab8_pass']} ledger={trial['snapshot']['refund_vnd']} "
              f"status={trial['result']['status']} fixed={probe['fixed']['lab8_pass']}")
        for i, event in enumerate(trial["events"], 1):
            print(f"  {i} {event['kind']} {json.dumps(event['payload'], ensure_ascii=False)}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
