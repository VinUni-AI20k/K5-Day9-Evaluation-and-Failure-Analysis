"""Run M3 graders on public variants and generate reviewable evidence.

Run in src/: python -m scripts.collect_m3_evidence
The official lab9.mutation --detect remains unchanged and is run separately.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic_evals.evaluators import EvaluatorContext

from lab8.console import utf8_stdio
from lab8.shapes import SHAPES
from lab9 import variants
from lab9.eval import SPEC, load_spec, load_world, make_task, run_eval
from lab9.graders import GRADERS, ReplyAmountCorrect
from lab9.variant_agent import make_shape


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main() -> int:
    utf8_stdio()
    variants.register()
    # A supplied bug toggle, registered only in this process; no variant source changes.
    SHAPES["m3_misreport"] = make_shape("m3_misreport", {"no_override", "misreport"})
    spec = load_spec()
    sources = [SPEC, Path(spec["eval_set"]), Path(spec["labels"]), Path("lab9/graders.py"),
               Path("lab9/stats.py"), Path("lab9/eval.py"), Path("lab9/variant_agent.py"),
               Path("lab9/variants.py"), Path("lab9/mutation.py"), Path("data/public_claims.jsonl"),
               Path("data/public_world_state.json")]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    now = datetime.now(timezone(timedelta(hours=7)))
    summary = {
        "run_id": f"M3-{now:%Y%m%d}-" + hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest()[:12],
        "manifest": {"generated_at": now.isoformat(), "backend": "MockLLM",
                     "seeds": spec["seeds"], "source_sha256": hashes,
                     "metric_spec_version": spec["metric_spec_version"]},
        "reports": {},
    }
    bad_value = {m["id"]: "max" in m.get("threshold", {}) for m in spec["metrics"]
                 if m["id"] in GRADERS and m["id"] != "pass_rate"}

    def flagged(row):
        return [mid for mid, bad in bad_value.items() if row[mid] is bad]

    reports = {}
    for shape in ("swarm", "fixed", "seeded_regression", "honest_refactor", "m3_misreport"):
        report = run_eval(shape, spec)
        if report["evaluator_failures"]:
            raise RuntimeError(f"{shape}: grader failures {report['evaluator_failures']}")
        if len(report["rows"]) != report["manifest"]["items"] * len(spec["seeds"]):
            raise RuntimeError(f"{shape}: incomplete report")
        path = Path("reports") / f"eval_m3_{shape}.json"
        write_json(path, report)
        reports[shape] = report
        summary["reports"][shape] = {
            "path": str(path), "run_id": report["run_id"], "trials": len(report["rows"]),
            "metrics": report["metrics"], "evaluator_failures": report["evaluator_failures"],
        }
        print(shape, report["metrics"])
    broken = [r for r in reports["seeded_regression"]["rows"] if r["pass_rate"] is False]
    detected = [r for r in broken if flagged(r)]
    fixed = reports["fixed"]["rows"]
    false_alarms = [r for r in fixed if flagged(r)]
    summary["detection"] = {
        "definition": "failing seeded_regression rows flagged by any grader except pass_rate",
        "failing_trials": len(broken), "detected_trials": len(detected),
        "rate": len(detected) / len(broken) if broken else 0.0,
        "missed": [r for r in broken if not flagged(r)],
        "flagged_metrics": [{"item_id": r["item_id"], "seed": r["seed"], "metrics": flagged(r)}
                            for r in broken],
    }
    summary["false_alarms"] = {"fixed_trials": len(fixed), "flagged_trials": len(false_alarms),
                               "rate": len(false_alarms) / len(fixed), "rows": false_alarms}
    honest = reports["honest_refactor"]["rows"]
    summary["honest_refactor"] = {"trials": len(honest), "flagged_trials": sum(bool(flagged(r)) for r in honest)}
    fm08 = reports["m3_misreport"]["rows"]
    summary["fm08"] = {
        "lab8_passed_trials": sum(r["pass_rate"] for r in fm08),
        "reply_mismatch_trials": sum(not r["reply_amount_correct"] for r in fm08),
        "mismatch_items": sorted({r["item_id"] for r in fm08 if not r["reply_amount_correct"]}),
    }
    world, claims = load_world(spec)
    labels = json.loads(Path(spec["labels"]).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="lab9-m3-", ignore_cleanup_errors=True) as tmp:
        trial = make_task("m3_misreport", world, claims, labels, Path(tmp))({"claim_id": "C-008", "seed": 11})
    context = EvaluatorContext(name="FM-08", inputs={}, metadata=None, expected_output=labels["C-008"],
                               output=trial, duration=0.0, _span_tree=None, attributes={}, metrics={})
    grade = ReplyAmountCorrect().evaluate(context)
    summary["fm08_probe"] = {
        "claim_id": "C-008", "seed": 11, "label": labels["C-008"],
        "result": trial["result"], "events": trial["events"], "snapshot": trial["snapshot"],
        "lab8_pass": trial["lab8_pass"], "reply_amount_correct": grade.value, "reason": grade.reason,
    }
    summary["passed"] = (summary["detection"]["rate"] >= 0.8
                         and summary["false_alarms"]["rate"] <= 0.1
                         and summary["honest_refactor"]["flagged_trials"] == 0
                         and summary["fm08"]["reply_mismatch_trials"] > 0)
    path = Path("reports/m3_grader_validation.json")
    write_json(path, summary)
    print(f"{summary['run_id']}: detection {len(detected)}/{len(broken)}, false alarms {len(false_alarms)}/{len(fixed)}")
    print(f"wrote {path}; passed={summary['passed']}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
