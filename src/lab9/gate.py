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
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return []  # A new eval set needs a new baseline and can choose new thresholds.
    problems: list[str] = []
    for group, key_fields in (("metric", ("id",)), ("slice", ("name", "metric"))):
        field = "metrics" if group == "metric" else "slices"
        current = {tuple(x.get(k) for k in key_fields): x for x in spec.get(field, [])}
        previous = {tuple(x.get(k) for k in key_fields): x for x in base_spec.get(field, [])}
        for key, old in previous.items():
            name = "/".join(str(x) for x in key)
            new = current.get(key)
            if new is None:
                problems.append(f"{group} {name} removed from spec")
                continue
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"{group} {name} changed from blocking to non-blocking")
            if group == "metric" and old.get("kind") != new.get("kind"):
                problems.append(f"metric {name} changed kind")
            old_th = old.get("threshold", {}) if group == "metric" else old
            new_th = new.get("threshold", {}) if group == "metric" else new
            for threshold in ("min", "max", "max_increase"):
                if threshold not in old_th:
                    continue
                if threshold not in new_th:
                    problems.append(f"{group} {name} removed {threshold}")
                elif (threshold == "min" and new_th[threshold] < old_th[threshold]) or (
                    threshold != "min" and new_th[threshold] > old_th[threshold]
                ):
                    problems.append(f"{group} {name} loosened {threshold}")
            if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
                problems.append(f"{group} {name} removed no_significant_drop")
    return problems


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
    if base_spec is not None:
        problems.extend(_ratchet_problems(spec, base_spec))
    manifest = pr.get("manifest", {})
    base_manifest = base.get("manifest", {})
    rows, base_rows = pr.get("rows"), base.get("rows")
    if not isinstance(rows, list) or not isinstance(base_rows, list):
        return [*problems, "report rows missing or invalid"]
    seeds, base_seeds = manifest.get("seeds"), base_manifest.get("seeds")
    items, base_items = manifest.get("items"), base_manifest.get("items")
    if not isinstance(seeds, list) or not isinstance(base_seeds, list) or not isinstance(items, int):
        return [*problems, "manifest items or seeds missing"]
    if items != base_items or seeds != base_seeds:
        problems.append("manifest items or seeds differ from baseline")
    if len(seeds) != len(set(seeds)):
        problems.append("duplicate seeds in manifest")
    if len(rows) != items * len(seeds):
        problems.append("row count differs from manifest items × seeds")
    if isinstance(base_items, int) and len(base_rows) != base_items * len(base_seeds):
        problems.append("baseline row count differs from its manifest")

    def row_keys(report_rows: list[dict]) -> Counter:
        return Counter((r.get("item_id"), r.get("seed")) for r in report_rows)

    keys, base_keys = row_keys(rows), row_keys(base_rows)
    if any(n > 1 for n in keys.values()):
        problems.append("duplicate (item_id, seed) rows")
    if keys != base_keys:
        problems.append("(item_id, seed) rows differ from baseline")
    baseline_slices = {(r.get("item_id"), r.get("seed")): r.get("slices", []) for r in base_rows}
    if any(r.get("slices", []) != baseline_slices.get((r.get("item_id"), r.get("seed"))) for r in rows):
        problems.append("row slice tags differ from baseline")
    if pr.get("evaluator_failures"):
        problems.append("evaluator failures present")

    metrics = pr.get("metrics", {})
    if not isinstance(metrics, dict):
        return [*problems, "report metrics missing or invalid"]
    for name, value in metrics.items():
        if isinstance(value, (int, float)) and not math.isfinite(value):
            problems.append(f"metric {name} is NaN or infinite")
    spec_ids = {m["id"] for m in spec.get("metrics", [])}
    for name in spec_ids:
        if metrics.get(name) is None:
            problems.append(f"metric {name} missing")

    # Aggregate metrics such as pass_hat_5 have no per-row field; use the baseline
    # to identify the metrics that must be present on every graded row.
    row_metric_ids = {name for name in spec_ids if any(name in r for r in base_rows)}
    for i, row in enumerate(rows):
        for name in row_metric_ids:
            value = row.get(name)
            if value is None or (isinstance(value, (int, float)) and not math.isfinite(value)):
                problems.append(f"row {i} has missing or non-finite {name}")
    if not problems and rows:
        # A hand-edited aggregate must not overrule the evidence in its rows.
        try:
            derived = aggregate([{**r, "cost": r.get("cost", 0)} for r in rows],
                                sorted(row_metric_ids), k_values=spec.get("pass_k", []))
            for name in spec_ids & derived.keys():
                if name == "cost_per_success" and any("cost" not in r for r in rows):
                    problems.append("row cost missing")
                elif not math.isclose(float(metrics[name]), float(derived[name]), abs_tol=1e-4):
                    problems.append(f"metric {name} differs from row aggregate")
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            problems.append(f"cannot recompute metrics from rows: {exc}")
    return problems


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
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        identity = f"slice:{name}/{metric}"
        current = per_item(pr, metric, slice_name=name)
        previous = per_item(base, metric, slice_name=name)
        value = sum(current.values()) / len(current) if current else None
        failed = value is None
        notes = []
        if value is None:
            notes.append("no scored items")
        elif "min" in entry and value < entry["min"]:
            failed = True
            notes.append(f"below min {entry['min']}")
        if entry.get("no_significant_drop") and value is not None:
            # A paired comparison needs the same items in both reports.
            if set(current) != set(previous):
                failed = True
                notes.append("item set differs from baseline")
            else:
                keys = sorted(current)
                delta, lo, hi = stats.paired_bootstrap(
                    [current[k] for k in keys], [previous[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95),
                )
                notes.append(f"Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]")
                if hi < 0:
                    failed = True
        if failed and entry.get("blocking"):
            blocked.append(identity)
        verdict = "BLOCK" if failed and entry.get("blocking") else "warn" if failed else "ok"
        lines.append(f"  {identity:<34} {value!s:<8} min {entry.get('min', '—')!s:<6} "
                     f"{' · '.join(notes):<45} {verdict}")
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
