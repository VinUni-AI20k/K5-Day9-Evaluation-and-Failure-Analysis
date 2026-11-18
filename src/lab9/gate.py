"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item



def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7: validate report integrity and prevent threshold loosening."""
    import math

    problems: list[str] = []

    manifest = pr.get("manifest", {})
    base_manifest = base.get("manifest", {})

    items = manifest.get("items")
    seeds = manifest.get("seeds") or []
    expected_rows = items * len(seeds) if isinstance(items, int) else None
    # 0. Report rows must match the authoritative eval-set in the spec.
    from lab9.evalset import load_jsonl, sha12

    eval_set_name = spec.get("eval_set")

    if eval_set_name:
        expected_path = Path(eval_set_name)

        # Both PR and baseline must reference the spec-defined eval set.
        for label, report_manifest in (
            ("PR", manifest),
            ("baseline", base_manifest),
        ):
            report_path = report_manifest.get("eval_set")

            if not report_path:
                problems.append(f"{label} manifest is missing eval_set")
            elif Path(report_path) != expected_path:
                problems.append(
                    f"{label} eval_set mismatch: expected {expected_path}, got {report_path}"
                )

        if not expected_path.is_file():
            problems.append(f"authoritative eval set file not found: {expected_path}")
        else:
            actual_sha = sha12(expected_path)

            for label, report_manifest in (
                ("PR", manifest),
                ("baseline", base_manifest),
            ):
                if report_manifest.get("eval_set_sha") != actual_sha:
                    problems.append(
                        f"{label} eval set SHA mismatch: "
                        f"expected {actual_sha}, "
                        f"got {report_manifest.get('eval_set_sha')}"
                    )

            expected_item_ids = {
                str(item["item_id"])
                for item in load_jsonl(expected_path)
            }
            actual_item_ids = {
                str(row.get("item_id"))
                for row in pr.get("rows", [])
            }

            if actual_item_ids != expected_item_ids:
                missing = sorted(expected_item_ids - actual_item_ids)
                unexpected = sorted(actual_item_ids - expected_item_ids)
                problems.append(
                    f"item IDs mismatch: missing={missing}, unexpected={unexpected}"
                )

    # 1. Metric values must be finite numbers.
    for metric, value in pr.get("metrics", {}).items():
        if isinstance(value, (int, float)) and not math.isfinite(value):
            problems.append(f"metric {metric} is not finite: {value}")

    # 2. PR must contain exactly items x seeds rows.
    rows = pr.get("rows", [])
    if expected_rows is None or len(rows) != expected_rows:
        problems.append(
            f"row count mismatch: expected {expected_rows}, got {len(rows)}"
        )

    # 3. PR and baseline must contain the same (item_id, seed) pairs.
    def row_keys(report: dict) -> list[tuple[str, int]]:
        return [
            (str(row.get("item_id")), row.get("seed"))
            for row in report.get("rows", [])
        ]

    pr_keys = row_keys(pr)
    base_keys = row_keys(base)

    if len(pr_keys) != len(set(pr_keys)):
        problems.append("PR contains duplicate (item_id, seed) rows")

    if set(pr_keys) != set(base_keys):
        problems.append("PR and baseline (item_id, seed) sets differ")

    # 4. Evaluator failures must not be silently accepted.
    failures = pr.get("evaluator_failures") or []
    if failures:
        problems.append(f"evaluator_failures is non-empty ({len(failures)})")

    # 5. A graded metric must not have missing values in any row.
    graded_metrics = {
        metric["id"]
        for metric in spec.get("metrics", [])
        if metric.get("grader")
        and metric.get("level") != "system"
        and metric["id"] not in {"pass_hat_5", "pass_5"}
    }

    for metric in sorted(graded_metrics):
        missing = sum(row.get(metric) is None for row in rows)
        if missing:
            problems.append(f"metric {metric} has {missing} missing row value(s)")

    # 6. Slice tags must remain identical for every item.
    def item_slices(report: dict) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for row in report.get("rows", []):
            item_id = str(row.get("item_id"))
            tags = set(row.get("slices") or [])
            if item_id in result and result[item_id] != tags:
                result[item_id] = result[item_id] | tags
            else:
                result[item_id] = tags
        return result

    if item_slices(pr) != item_slices(base):
        problems.append("item slice tags differ from baseline")

    # 7. Threshold ratchet applies only to the same eval-set version.
    same_version = (
        spec.get("eval_set_version")
        == (base_spec or {}).get("eval_set_version")
    )

    if base_spec is not None and same_version:
        base_metrics = {
            metric["id"]: metric
            for metric in base_spec.get("metrics", [])
        }

        current_metrics = {
            metric["id"]: metric
            for metric in spec.get("metrics", [])
        }

        # A metric may not disappear.
        for metric_id, old in base_metrics.items():
            if metric_id not in current_metrics:
                problems.append(f"metric {metric_id} was removed")
                continue

            new = current_metrics[metric_id]
            old_threshold = old.get("threshold", {})
            new_threshold = new.get("threshold", {})

            # max may not rise.
            if "max" in old_threshold:
                if "max" not in new_threshold or new_threshold["max"] > old_threshold["max"]:
                    problems.append(f"metric {metric_id} max threshold was loosened")

            # min may not fall.
            if "min" in old_threshold:
                if "min" not in new_threshold or new_threshold["min"] < old_threshold["min"]:
                    problems.append(f"metric {metric_id} min threshold was loosened")

            # max_increase may not rise.
            if "max_increase" in old_threshold:
                if (
                    "max_increase" not in new_threshold
                    or new_threshold["max_increase"] > old_threshold["max_increase"]
                ):
                    problems.append(f"metric {metric_id} max_increase was loosened")

            # no_significant_drop may not be disabled.
            if old_threshold.get("no_significant_drop") and not new_threshold.get("no_significant_drop"):
                problems.append(f"metric {metric_id} no_significant_drop was disabled")

            # A blocking metric may not become non-blocking.
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"metric {metric_id} was made non-blocking")

        # Slice ratchet.
        base_slices = {
            (s["name"], s["metric"]): s
            for s in base_spec.get("slices", [])
        }
        current_slices = {
            (s["name"], s["metric"]): s
            for s in spec.get("slices", [])
        }

        for key, old in base_slices.items():
            name, metric = key

            if key not in current_slices:
                problems.append(f"slice {name}/{metric} was removed")
                continue

            new = current_slices[key]

            if "min" in old:
                if "min" not in new or new["min"] < old["min"]:
                    problems.append(f"slice {name}/{metric} min threshold was loosened")

            if old.get("no_significant_drop") and not new.get("no_significant_drop"):
                problems.append(f"slice {name}/{metric} no_significant_drop was disabled")

            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"slice {name}/{metric} was made non-blocking")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """Check capability regressions on important slices."""
    blocked: list[str] = []
    lines: list[str] = []

    bs = spec.get("bootstrap", {})

    for s in spec.get("slices", []):
        name = s["name"]
        metric = s["metric"]
        threshold = s.get("min")
        no_significant_drop = s.get("no_significant_drop", False)
        is_blocking = s.get("blocking", False)

        pr_items = per_item(pr, metric, slice_name=name)
        base_items = per_item(base, metric, slice_name=name)

        if not pr_items:
            lines.append(f"  slice:{name}/{metric:<18} MISSING PR slice data")
            if is_blocking:
                blocked.append(f"slice:{name}/{metric}")
            continue

        value = sum(pr_items.values()) / len(pr_items)
        verdict = "ok"
        note = ""

        if threshold is not None and value < threshold:
            verdict = "fail"

        if no_significant_drop:
            keys = sorted(set(pr_items) & set(base_items))

            if not keys:
                verdict = "missing"
                note = "no paired items with baseline"
            else:
                d, lo, hi = stats.paired_bootstrap(
                    [pr_items[k] for k in keys],
                    [base_items[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95),
                )

                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"

                if hi < 0 or (hi == 0 and d < 0):
                    verdict = "fail"

        if verdict != "ok" and is_blocking:
            blocked.append(f"slice:{name}/{metric}")

        label = "ok" if verdict == "ok" else (
            "MISSING" if verdict == "missing" else
            ("BLOCK" if is_blocking else "warn")
        )

        lines.append(
            f"  slice:{name}/{metric:<18} {value:.4f} "
            f"min={threshold} {note:<28} {label}"
        )

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
