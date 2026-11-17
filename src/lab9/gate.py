"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    # 1. Check for NaN or inf in metrics
    for metric_name, metric_value in pr.get("metrics", {}).items():
        if isinstance(metric_value, float):
            if math.isnan(metric_value) or math.isinf(metric_value):
                problems.append(f"metric {metric_name} has invalid value {metric_value}")

    # 2. Check row count against manifest
    manifest = pr.get("manifest", {})
    manifest_item_count = manifest.get("items")
    manifest_seeds = manifest.get("seeds", [])
    if manifest_item_count is not None and manifest_seeds:
        expected_total_rows = manifest_item_count * len(manifest_seeds)
        actual_total_rows = len(pr.get("rows", []))
        if actual_total_rows != expected_total_rows:
            problems.append(f"expected {expected_total_rows} rows from manifest, got {actual_total_rows}")

    # 3. Check (item_id, seed) set against baseline
    pr_case_set = {(row["item_id"], row["seed"]) for row in pr.get("rows", [])}
    base_case_set = {(row["item_id"], row["seed"]) for row in base.get("rows", [])}
    if pr_case_set != base_case_set:
        problems.append("PR (item_id, seed) cases differ from baseline cases")

    # 4. Check evaluator failures and missing values in rows for graded metrics
    if pr.get("evaluator_failures"):
        problems.append(f"PR has {len(pr['evaluator_failures'])} evaluator failure(s)")

    spec_metric_ids = [m["id"] for m in spec.get("metrics", [])]
    for row in pr.get("rows", []):
        for metric_id in spec_metric_ids:
            if metric_id in row and row[metric_id] is None:
                problems.append(f"row {row.get('item_id')}@{row.get('seed')} has None for metric {metric_id}")

    # 5. Check ratchet against base_spec
    if base_spec is not None:
        if spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            base_metrics_map = {m["id"]: m for m in base_spec.get("metrics", [])}
            spec_metrics_map = {m["id"]: m for m in spec.get("metrics", [])}
            for base_metric_id, base_metric in base_metrics_map.items():
                if base_metric_id not in spec_metrics_map:
                    problems.append(f"metric {base_metric_id} from base_spec missing in spec")
                else:
                    spec_metric = spec_metrics_map[base_metric_id]
                    if base_metric.get("blocking") and not spec_metric.get("blocking"):
                        problems.append(f"metric {base_metric_id} blocking was disabled")
                    base_threshold = base_metric.get("threshold", {})
                    spec_threshold = spec_metric.get("threshold", {})
                    if "min" in base_threshold:
                        if "min" not in spec_threshold or spec_threshold["min"] < base_threshold["min"]:
                            problems.append(f"metric {base_metric_id} min threshold was loosened")
                    if "max" in base_threshold:
                        if "max" not in spec_threshold or spec_threshold["max"] > base_threshold["max"]:
                            problems.append(f"metric {base_metric_id} max threshold was loosened")
                    if base_threshold.get("no_significant_drop") and not spec_threshold.get("no_significant_drop"):
                        problems.append(f"metric {base_metric_id} dropped no_significant_drop")

            base_slices_map = {s["name"]: s for s in base_spec.get("slices", [])}
            spec_slices_map = {s["name"]: s for s in spec.get("slices", [])}
            for base_slice_name, base_slice in base_slices_map.items():
                if base_slice_name not in spec_slices_map:
                    problems.append(f"slice {base_slice_name} from base_spec missing in spec")
                else:
                    spec_slice = spec_slices_map[base_slice_name]
                    if base_slice.get("blocking") and not spec_slice.get("blocking"):
                        problems.append(f"slice {base_slice_name} blocking was disabled")
                    if "min" in base_slice:
                        if "min" not in spec_slice or spec_slice["min"] < base_slice["min"]:
                            problems.append(f"slice {base_slice_name} min threshold was loosened")
                    if base_slice.get("no_significant_drop") and not spec_slice.get("no_significant_drop"):
                        problems.append(f"slice {base_slice_name} dropped no_significant_drop")

    # 6. Check slice tags consistency
    pr_item_slices = {row["item_id"]: set(row.get("slices", [])) for row in pr.get("rows", [])}
    base_item_slices = {row["item_id"]: set(row.get("slices", [])) for row in base.get("rows", [])}
    for item_id, base_tags in base_item_slices.items():
        if item_id in pr_item_slices and pr_item_slices[item_id] != base_tags:
            problems.append(f"item {item_id} slice tags differ from baseline")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked_slices: list[str] = []
    report_lines: list[str] = []
    bootstrap_config = spec.get("bootstrap", {})

    for slice_spec in spec.get("slices", []):
        slice_name = slice_spec["name"]
        metric_id = slice_spec.get("metric", "pass_rate")
        min_threshold = slice_spec.get("min")
        no_significant_drop = slice_spec.get("no_significant_drop", False)
        is_blocking = slice_spec.get("blocking", True)

        pr_items = per_item(pr, metric_id, slice_name=slice_name)
        base_items = per_item(base, metric_id, slice_name=slice_name)

        if pr_items:
            slice_mean = float(sum(pr_items.values()) / len(pr_items))
        else:
            slice_mean = None

        verdict = "ok"
        difference_note = ""

        if slice_mean is None:
            verdict = "missing"
        else:
            if min_threshold is not None and slice_mean < min_threshold:
                verdict = "fail"

            if no_significant_drop:
                common_keys = sorted(set(pr_items.keys()) & set(base_items.keys()))
                if common_keys:
                    diff_mean, ci_low, ci_high = stats.paired_bootstrap(
                        [pr_items[k] for k in common_keys],
                        [base_items[k] for k in common_keys],
                        n_resamples=bootstrap_config.get("n_resamples", 1000),
                        rng=bootstrap_config.get("rng", 2027),
                    )
                    difference_note = f"Δ {diff_mean:+.3f} CI [{ci_low:+.3f}, {ci_high:+.3f}]"
                    if ci_high < 0.0:
                        verdict = "fail"

        slice_id = f"slice:{slice_name}/{metric_id}"
        if verdict != "ok" and is_blocking:
            blocked_slices.append(slice_id)

        label_verdict = {"ok": "ok", "missing": "MISSING"}.get(
            verdict, "BLOCK" if is_blocking else "warn"
        )
        report_lines.append(
            f"  {slice_id:<22} {slice_mean!s:<8} {json.dumps(slice_spec):<40} {difference_note:<28} {label_verdict}"
        )

    return blocked_slices, report_lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
