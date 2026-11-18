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
    import math

    from lab9.eval import aggregate
    from lab9.graders import GRADERS

    problems: list[str] = []
    pm, bm = pr.get("manifest") or {}, base.get("manifest") or {}
    rows, brows = pr.get("rows") or [], base.get("rows") or []

    # 1. NaN / inf metric values
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {k} is {v}")

    # 2. row count vs manifest, manifest vs baseline, duplicated rows
    want = (pm.get("items") or 0) * len(pm.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {pm.get('items')} items x {len(pm.get('seeds') or [])} seeds = {want}")
    if pm.get("items") != bm.get("items") or list(pm.get("seeds") or []) != list(bm.get("seeds") or []):
        problems.append(f"manifest differs from baseline: items {pm.get('items')} vs {bm.get('items')}, "
                        f"seeds {pm.get('seeds')} vs {bm.get('seeds')}")
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    if len(keys) != len(set(keys)):
        problems.append(f"{len(keys) - len(set(keys))} duplicated (item_id, seed) row(s)")

    # 3. (item_id, seed) set must equal the baseline's
    bkeys = {(r.get("item_id"), r.get("seed")) for r in brows}
    if set(keys) != bkeys:
        problems.append(f"(item, seed) set differs from baseline: {len(set(keys) - bkeys)} extra, "
                        f"{len(bkeys - set(keys))} missing")

    # 4. crashed graders: evaluator_failures, or None for a graded spec metric
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s)")
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    nones = sorted({m for r in rows for m in graded if m in r and r[m] is None})
    missing = sorted({m for r in rows for m in graded if m not in r}) if rows else []
    if nones:
        problems.append(f"None values for graded metric(s) {nones}")
    if missing:
        problems.append(f"rows lack graded metric(s) {missing}")

    # 5. ratchet: same eval-set version => thresholds may only get stricter
    if base_spec and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        new = {m["id"]: m for m in spec.get("metrics", [])}
        for old in base_spec.get("metrics", []):
            mid, cur = old["id"], new.get(old["id"])
            if cur is None:
                problems.append(f"ratchet: metric {mid} removed")
                continue
            o, c = old.get("threshold") or {}, cur.get("threshold") or {}
            for k in ("max", "max_increase"):
                if k in o and (k not in c or c[k] > o[k]):
                    problems.append(f"ratchet: {mid}.{k} {o[k]} -> {c.get(k)}")
            if "min" in o and ("min" not in c or c["min"] < o["min"]):
                problems.append(f"ratchet: {mid}.min {o['min']} -> {c.get('min')}")
            if o.get("no_significant_drop") and not c.get("no_significant_drop"):
                problems.append(f"ratchet: {mid} dropped no_significant_drop")
            if old.get("blocking") and not cur.get("blocking"):
                problems.append(f"ratchet: {mid} no longer blocking")
        new_sl = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
        for old in base_spec.get("slices") or []:
            key = (old["name"], old["metric"])
            cur = new_sl.get(key)
            if cur is None:
                problems.append(f"ratchet: slice {key[0]}/{key[1]} removed")
                continue
            if "min" in old and ("min" not in cur or cur["min"] < old["min"]):
                problems.append(f"ratchet: slice {key[0]}/{key[1]}.min {old['min']} -> {cur.get('min')}")
            if old.get("no_significant_drop") and not cur.get("no_significant_drop"):
                problems.append(f"ratchet: slice {key[0]}/{key[1]} dropped no_significant_drop")
            if old.get("blocking") and not cur.get("blocking"):
                problems.append(f"ratchet: slice {key[0]}/{key[1]} no longer blocking")

    # 6. slice tags of each item must match the baseline's
    btags = {r.get("item_id"): sorted(r.get("slices") or []) for r in brows}
    relabelled = sorted({r.get("item_id") for r in rows
                         if r.get("item_id") in btags and sorted(r.get("slices") or []) != btags[r.get("item_id")]})
    if relabelled:
        problems.append(f"slice tags differ from baseline for {relabelled[:5]}")

    # 7. reported metrics must be what the rows say (hand-edited report)
    if rows and all("cost" in r for r in rows):
        ids = [m for m in graded if all(m in r for r in rows)]
        try:
            again = aggregate(rows, ids, k_values=spec.get("pass_k", []))
        except Exception as exc:                      # unreadable rows are themselves a problem
            problems.append(f"cannot recompute metrics from rows: {exc}")
            again = {}
        for k, v in again.items():
            got = (pr.get("metrics") or {}).get(k)
            if isinstance(v, (int, float)) and isinstance(got, (int, float)) and abs(v - got) > 1e-3:
                problems.append(f"metric {k} reported {got} but rows give {v}")
            elif (v is None) != (got is None) and k in (pr.get("metrics") or {}):
                problems.append(f"metric {k} reported {got} but rows give {v}")
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
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        if not a:
            verdict, val, note = "missing", None, "no items in slice"
        else:
            val = round(sum(a.values()) / len(a), 4)
            verdict, note = "ok", f"n={len(a)}"
            if "min" in sl and val < sl["min"]:
                verdict = "fail"
            keys = sorted(set(a) & set(b))
            if sl.get("no_significant_drop") and keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000),
                                                   rng=bs.get("rng", 2027),
                                                   confidence=bs.get("confidence", 0.95))
                note += f" Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        lines.append(f"  {sid:<34} {val!s:<8} {json.dumps(th):<40} {note:<36} {label}")
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
