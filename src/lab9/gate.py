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
    def finite_tree(value, path: str) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            problems.append(f"{path} is non-finite")
        elif isinstance(value, dict):
            for key, child in value.items():
                finite_tree(child, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for i, child in enumerate(value):
                finite_tree(child, f"{path}[{i}]")

    finite_tree(pr.get("metrics", {}), "metrics")
    rows = pr.get("rows") or []
    manifest = pr.get("manifest") or {}
    seeds = manifest.get("seeds") or []
    items = manifest.get("items")
    if not isinstance(items, int) or items < 0:
        problems.append("manifest.items is missing or invalid")
    elif len(rows) != items * len(seeds):
        problems.append(f"row count {len(rows)} != manifest items×seeds {items * len(seeds)}")
    def row_keys(report: dict) -> list[tuple[str, int]]:
        result = []
        for row in report.get("rows") or []:
            try:
                result.append((str(row["item_id"]), int(row["seed"])))
            except (KeyError, TypeError, ValueError):
                problems.append("row missing valid item_id/seed")
        return result
    pr_keys, base_keys = row_keys(pr), row_keys(base)
    if len(set(pr_keys)) != len(pr_keys):
        problems.append("duplicate (item_id, seed) rows")
    if set(pr_keys) != set(base_keys):
        problems.append("PR (item_id, seed) set differs from baseline")
    if pr.get("evaluator_failures"):
        problems.append("evaluator_failures is non-empty")
    row_metric_ids = [m.get("id") for m in spec.get("metrics", [])
                      if m.get("id") and m.get("grader") != "lab8.metrics.summarize"
                      and m.get("kind") != "system"]
    for mid in row_metric_ids:
        if mid not in (pr.get("metrics") or {}):
            problems.append(f"metric {mid} missing from report metrics")
        for index, row in enumerate(rows):
            if mid not in row or row[mid] is None:
                problems.append(f"row {index} metric {mid} is missing/None")
                break
            if not isinstance(row[mid], bool):
                problems.append(f"row {index} metric {mid} is not boolean")
                break
    # A report cannot move a row out of a protected slice by editing its tags.
    base_tags = {str(r.get("item_id")): tuple(sorted(r.get("slices") or [])) for r in base.get("rows") or []}
    pr_tags = {str(r.get("item_id")): tuple(sorted(r.get("slices") or [])) for r in rows}
    for item_id in set(base_tags) & set(pr_tags):
        if base_tags[item_id] != pr_tags[item_id]:
            problems.append(f"slice tags changed for {item_id}")
            break

    # Same eval-set version means the PR may only tighten policy.
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        old_metrics = {m.get("id"): m for m in base_spec.get("metrics", [])}
        new_metrics = {m.get("id"): m for m in spec.get("metrics", [])}
        for mid, old in old_metrics.items():
            new = new_metrics.get(mid)
            if new is None:
                problems.append(f"metric {mid} removed from spec")
                continue
            old_th, new_th = old.get("threshold") or {}, new.get("threshold") or {}
            if "max" in old_th and ("max" not in new_th or new_th["max"] > old_th["max"]):
                problems.append(f"metric {mid} max threshold loosened/removed")
            if "min" in old_th and ("min" not in new_th or new_th["min"] < old_th["min"]):
                problems.append(f"metric {mid} min threshold loosened/removed")
            if "max_increase" in old_th and ("max_increase" not in new_th
                                               or new_th["max_increase"] > old_th["max_increase"]):
                problems.append(f"metric {mid} max_increase threshold loosened/removed")
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"metric {mid} changed from blocking to non-blocking")
            if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
                problems.append(f"metric {mid} removed no_significant_drop")
        old_slices = {s.get("name"): s for s in base_spec.get("slices", [])}
        new_slices = {s.get("name"): s for s in spec.get("slices", [])}
        for name, old in old_slices.items():
            new = new_slices.get(name)
            if new is None:
                problems.append(f"slice {name} removed from spec")
                continue
            for key in ("metric", "blocking"):
                if old.get(key) != new.get(key) and (key != "blocking" or old.get(key)):
                    problems.append(f"slice {name} changed {key}")
            if "min" in old and ("min" not in new or new["min"] < old["min"]):
                problems.append(f"slice {name} min threshold loosened/removed")
            if "max" in old and ("max" not in new or new["max"] > old["max"]):
                problems.append(f"slice {name} max threshold loosened/removed")
            if old.get("no_significant_drop") and not new.get("no_significant_drop"):
                problems.append(f"slice {name} removed no_significant_drop")
    return list(dict.fromkeys(problems))


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for rule in spec.get("slices", []):
        name, metric = rule["name"], rule["metric"]
        values = per_item(pr, metric, slice_name=name)
        base_values = per_item(base, metric, slice_name=name)
        val = sum(values.values()) / len(values) if values else None
        verdicts = []
        if "min" in rule and (val is None or val < rule["min"]):
            verdicts.append(f"below min {rule['min']}")
        note = ""
        if rule.get("no_significant_drop"):
            keys = sorted(set(values) & set(base_values))
            if not keys:
                verdicts.append("no paired slice items")
            else:
                d, lo, hi = stats.paired_bootstrap([values[k] for k in keys], [base_values[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdicts.append("significant drop")
        ident = f"slice:{name}/{metric}"
        if verdicts and rule.get("blocking"):
            blocked.append(ident)
        lines.append(f"  {ident:<35} {val!s:<8} min={rule.get('min')} {note} {'BLOCK' if verdicts and rule.get('blocking') else 'ok'}")
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
