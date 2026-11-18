"""Generate sanitized taxonomy evidence without editing the provided variants or Lab 8.

Run from src: python -m scripts.lab9_evidence
Each experiment uses the supplied make_shape factory and a fresh temporary database.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from lab8.shapes import SHAPES
from lab8.console import utf8_stdio
from lab9 import evalset
from lab9.eval import load_spec, load_world, make_task
from lab9.graders import GRADERS
from lab9.variant_agent import make_shape

CASES = [
    ("FM-01", "leaky_trace", "C-001"),
    ("FM-02", "ignore_denied", "C-007"),
    ("FM-03", "ticket_trust", "C-002"),
    ("FM-04", "sum_parts", "C-014"),
    ("FM-05", "pre_deducted", "C-014"),
    ("FM-06", "stale_clause", "C-006"),
    ("FM-07", "sibling_refund", "C-001"),
    ("FM-08", "misreport", "C-008"),
    ("FM-09", "no_override", "C-113"),
]


def main():
    utf8_stdio()
    spec = load_spec(Path("config/metric_spec_v2.yaml"))
    world, claims = load_world(spec)
    labels = json.loads(Path(spec["labels"]).read_text(encoding="utf-8"))
    evidence = []
    for mode, bug, claim in CASES:
        name = f"evidence_{bug}"
        shape = make_shape(name, {"no_override", bug})
        previous = SHAPES.get(name)
        SHAPES[name] = shape
        try:
            with tempfile.TemporaryDirectory(prefix="lab9-evidence-", ignore_cleanup_errors=True) as tmp:
                trial = make_task(name, world, claims, labels, Path(tmp))({"claim_id": claim, "seed": 11})
            ctx = SimpleNamespace(output=trial, expected_output=labels[claim])
            events = []
            for step, event in enumerate(trial["events"], 1):
                payload = event.get("payload")
                if event["kind"] == "debug_claim_row":
                    payload = {"redacted": True, "keys": sorted(payload)}
                events.append({"step": step, "kind": event["kind"], "payload": payload})
            evidence.append({"mode": mode, "experiment": name, "claim": claim, "seed": 11,
                "lab8_pass": trial["lab8_pass"], "reason": trial["lab8_reason"],
                "snapshot": trial["snapshot"], "unexpected_rows": trial["unexpected_rows"],
                "proposal_amount": trial["result"].get("proposal_amount"),
                "scores": {metric: grader().evaluate(ctx).value for metric, grader in GRADERS.items()},
                "events": events})
        finally:
            if previous is None:
                SHAPES.pop(name, None)
            else:
                SHAPES[name] = previous
    output = Path("reports/taxonomy_evidence.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({"eval_set_sha": evalset.sha12(Path(spec["eval_set"])),
                                 "cases": evidence}, ensure_ascii=False, indent=2), encoding="utf-8")
    for case in evidence:
        print(f"{case['mode']} {case['claim']}@11 {case['experiment']} "
              f"lab8_pass={case['lab8_pass']} ledger={case['snapshot']['refund_vnd']} "
              f"proposal={case['proposal_amount']} unexpected={case['unexpected_rows']}")
        for event in case["events"]:
            if event["kind"] not in {"handoff", "investigator"}:
                print(f"  {event['step']} {event['kind']} {event['payload']}")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
