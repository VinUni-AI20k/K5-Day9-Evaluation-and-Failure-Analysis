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
from lab9.eval import SPEC, aggregate, load_spec, per_item


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
    for report_name, report in (("pr", pr), ("baseline", base)):
        for metric, value in (report.get("metrics") or {}).items():
            if isinstance(value, (int, float)) and not math.isfinite(float(value)):
                problems.append(f"{report_name} metric {metric} is not finite")
        if report.get("evaluator_failures"):
            problems.append(f"{report_name} has evaluator_failures")

    def row_keys(report: dict) -> list[tuple[str, int] | None]:
        keys = []
        for row in report.get("rows") or []:
            item_id, seed = row.get("item_id"), row.get("seed")
            keys.append((str(item_id), seed) if item_id is not None and seed is not None else None)
        return keys

    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []
    pr_keys, base_keys = row_keys(pr), row_keys(base)
    for name, report, rows, keys in (
        ("pr", pr, pr_rows, pr_keys),
        ("baseline", base, base_rows, base_keys),
    ):
        manifest = report.get("manifest") or {}
        items, seeds = manifest.get("items"), manifest.get("seeds")
        if isinstance(items, int) and isinstance(seeds, list) and len(rows) != items * len(seeds):
            problems.append(f"{name} row count {len(rows)} != manifest items x seeds {items * len(seeds)}")
        if None in keys:
            problems.append(f"{name} has a row without item_id or seed")
        if len(set(keys)) != len(keys):
            problems.append(f"{name} has duplicate (item_id, seed) rows")

    if set(pr_keys) != set(base_keys):
        problems.append("PR (item_id, seed) rows differ from baseline")

    base_by_key = {key: row for key, row in zip(base_keys, base_rows) if key is not None}
    for key, row in zip(pr_keys, pr_rows):
        if key is None or key not in base_by_key:
            continue
        pr_slices = tuple(sorted(row.get("slices") or []))
        base_slices = tuple(sorted(base_by_key[key].get("slices") or []))
        if pr_slices != base_slices:
            problems.append(f"slice tags differ for {key[0]}@{key[1]}")
            break

    for metric in spec.get("metrics") or []:
        metric_id = metric.get("id")
        if not metric_id:
            continue
        is_row_metric = any(metric_id in row for row in base_rows)
        for index, row in enumerate(pr_rows):
            if is_row_metric and (metric_id not in row or row[metric_id] is None):
                problems.append(f"PR row {index} has missing graded metric {metric_id}")
                break

    for report_name, report, rows in (("pr", pr, pr_rows), ("baseline", base, base_rows)):
        if not rows or not report.get("run_id"):
            continue
        row_metric_ids = [
            metric["id"]
            for metric in spec.get("metrics") or []
            if metric.get("id") in rows[0]
        ]
        recomputed = aggregate(rows, row_metric_ids, k_values=spec.get("pass_k", []))
        saved = report.get("metrics") or {}
        for metric_id, expected_value in recomputed.items():
            actual_value = saved.get(metric_id)
            if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
                agrees = math.isfinite(float(actual_value)) and math.isclose(
                    float(actual_value), float(expected_value), rel_tol=1e-9, abs_tol=1e-9
                )
            else:
                agrees = actual_value == expected_value
            if not agrees:
                problems.append(f"{report_name} aggregate metric {metric_id} disagrees with rows")

    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        old_metrics = {m["id"]: m for m in base_spec.get("metrics") or [] if m.get("id")}
        new_metrics = {m["id"]: m for m in spec.get("metrics") or [] if m.get("id")}
        for metric_id in sorted(old_metrics.keys() - new_metrics.keys()):
            problems.append(f"ratchet removed metric {metric_id}")
        for metric_id in sorted(old_metrics.keys() & new_metrics.keys()):
            old, new = old_metrics[metric_id], new_metrics[metric_id]
            old_threshold = old.get("threshold") or {}
            new_threshold = new.get("threshold") or {}
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"ratchet made metric {metric_id} non-blocking")
            if old_threshold.get("no_significant_drop") and not new_threshold.get("no_significant_drop"):
                problems.append(f"ratchet removed no_significant_drop from {metric_id}")
            if "min" in old_threshold and (
                "min" not in new_threshold or new_threshold["min"] < old_threshold["min"]
            ):
                problems.append(f"ratchet lowered minimum for {metric_id}")
            if "max" in old_threshold and (
                "max" not in new_threshold or new_threshold["max"] > old_threshold["max"]
            ):
                problems.append(f"ratchet raised maximum for {metric_id}")
            if "max_increase" in old_threshold and (
                "max_increase" not in new_threshold
                or new_threshold["max_increase"] > old_threshold["max_increase"]
            ):
                problems.append(f"ratchet raised max_increase for {metric_id}")

        old_slices = {s["name"]: s for s in base_spec.get("slices") or [] if s.get("name")}
        new_slices = {s["name"]: s for s in spec.get("slices") or [] if s.get("name")}
        for name in sorted(old_slices.keys() - new_slices.keys()):
            problems.append(f"ratchet removed slice {name}")
        for name in sorted(old_slices.keys() & new_slices.keys()):
            old, new = old_slices[name], new_slices[name]
            if old.get("metric") != new.get("metric"):
                problems.append(f"ratchet changed metric for slice {name}")
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"ratchet made slice {name} non-blocking")
            if old.get("no_significant_drop") and not new.get("no_significant_drop"):
                problems.append(f"ratchet removed no_significant_drop from slice {name}")
            if "min" in old and ("min" not in new or new["min"] < old["min"]):
                problems.append(f"ratchet lowered minimum for slice {name}")
            if "max" in old and ("max" not in new or new["max"] > old["max"]):
                problems.append(f"ratchet raised maximum for slice {name}")

    return sorted(set(problems))


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    for rule in spec.get("slices") or []:
        name, metric = rule["name"], rule["metric"]
        pr_values = per_item(pr, metric, name)
        base_values = per_item(base, metric, name)
        if not pr_values:
            verdict = "MISSING"
            note = f"no PR items in slice {name}"
        else:
            value = sum(pr_values.values()) / len(pr_values)
            verdict = "ok"
            notes = [f"value={value:.3f}"]
            if "min" in rule and value < rule["min"]:
                verdict = "fail"
                notes.append(f"below min {rule['min']}")
            if rule.get("no_significant_drop"):
                common = sorted(pr_values.keys() & base_values.keys())
                if not common:
                    verdict = "MISSING"
                    notes.append("no paired baseline items")
                else:
                    bs = spec.get("bootstrap") or {}
                    delta, lo, hi = stats.paired_bootstrap(
                        [pr_values[key] for key in common],
                        [base_values[key] for key in common],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    notes.append(f"Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]")
                    if hi < 0:
                        verdict = "fail"
                        notes.append("significant drop")
            note = "; ".join(notes)
        is_blocking = bool(rule.get("blocking"))
        if verdict != "ok" and is_blocking:
            blocked.append(f"slice:{name}/{metric}")
        label = "BLOCK" if verdict != "ok" and is_blocking else ("warn" if verdict != "ok" else "ok")
        lines.append(f"  slice:{name}/{metric:<16} {note} [{label}]")
    return blocked, lines


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
