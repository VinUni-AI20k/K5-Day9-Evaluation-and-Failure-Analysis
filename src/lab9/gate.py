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


def _is_bad_number(v) -> bool:
    return isinstance(v, float) and (math.isnan(v) or math.isinf(v))


def _graded_ids(spec: dict) -> list[str]:
    from lab9.graders import GRADERS
    return [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Thresholds on the same eval-set version may only get stricter."""
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return []          # new eval-set version: new baseline, thresholds start over
    out: list[str] = []
    for key in ("eval_set", "labels", "seeds", "bootstrap", "adversarial_pack"):
        if key in base_spec and spec.get(key) != base_spec.get(key):
            out.append(f"ratchet: spec[{key!r}] changed on the same eval-set version")
    for k in base_spec.get("pass_k") or []:
        if k not in (spec.get("pass_k") or []):
            out.append(f"ratchet: pass_k {k} removed")

    def compare(what: str, old: dict, new: dict | None, th_old: dict, th_new: dict) -> None:
        if new is None:
            out.append(f"ratchet: {what} removed")
            return
        if old.get("blocking") and not new.get("blocking"):
            out.append(f"ratchet: {what} no longer blocking")
        for k in ("kind", "metric"):
            if k in old and new.get(k) != old.get(k):
                out.append(f"ratchet: {what} {k} changed {old.get(k)!r} -> {new.get(k)!r}")
        for k in ("max", "max_increase"):
            if k in th_old and (k not in th_new or th_new[k] > th_old[k]):
                out.append(f"ratchet: {what} {k} loosened {th_old[k]} -> {th_new.get(k)}")
        if "min" in th_old and ("min" not in th_new or th_new["min"] < th_old["min"]):
            out.append(f"ratchet: {what} min loosened {th_old['min']} -> {th_new.get('min')}")
        if th_old.get("no_significant_drop") and not th_new.get("no_significant_drop"):
            out.append(f"ratchet: {what} no_significant_drop dropped")

    new_m = {m["id"]: m for m in spec.get("metrics", [])}
    for m in base_spec.get("metrics", []):
        n = new_m.get(m["id"])
        compare(f"metric {m['id']}", m, n, m.get("threshold") or {}, (n or {}).get("threshold") or {})
    new_s = {(s["name"], s.get("metric", "pass_rate")): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        n = new_s.get((s["name"], s.get("metric", "pass_rate")))
        compare(f"slice {s['name']}/{s.get('metric', 'pass_rate')}", s, n, s, n or {})
    return out


def _slice_tags(rows: list[dict]) -> dict[str, set]:
    out: dict[str, set] = {}
    for r in rows:
        out.setdefault(r.get("item_id"), set()).update(r.get("slices") or [])
    return out


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Catches: NaN/inf metrics, dropped / duplicated / cherry-picked rows, crashed graders (None),
    metrics that do not follow from the rows, a loosened spec (ratchet) and relabelled slices."""
    problems: list[str] = []
    rows, brows = pr.get("rows") or [], base.get("rows") or []
    man, bman = pr.get("manifest") or {}, base.get("manifest") or {}
    metrics = pr.get("metrics") or {}

    # 1. metric values must be finite numbers, and none the baseline reports may vanish
    for k, v in metrics.items():
        if _is_bad_number(v):
            problems.append(f"metric {k} is {v}")
        elif v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
            problems.append(f"metric {k} is not a number: {v!r}")
    for m in spec.get("metrics", []):
        if m["id"] in (base.get("metrics") or {}) and m["id"] not in metrics:
            problems.append(f"metric {m['id']} missing from the PR report")

    # 2. row count = items x seeds, and the manifest matches the baseline's
    seeds = list(man.get("seeds") or [])
    if man.get("items") is None or len(rows) != man["items"] * len(seeds):
        problems.append(f"{len(rows)} rows != {man.get('items')} items x {len(seeds)} seeds")
    for k in ("items", "seeds", "eval_set"):
        if k in bman and man.get(k) != bman.get(k):
            problems.append(f"manifest {k} {man.get(k)!r} differs from the baseline's {bman.get(k)!r}")

    # 3. the (item, seed) set must be exactly the baseline's, with no duplicates
    pairs = [(r.get("item_id"), r.get("seed")) for r in rows]
    bpairs = {(r.get("item_id"), r.get("seed")) for r in brows}
    if len(pairs) != len(set(pairs)):
        problems.append(f"{len(pairs) - len(set(pairs))} duplicated (item, seed) row(s)")
    if set(pairs) != bpairs:
        miss, extra = bpairs - set(pairs), set(pairs) - bpairs
        problems.append(f"(item, seed) set differs from baseline: {len(miss)} missing, {len(extra)} extra")
    if seeds and {p[1] for p in pairs} != set(seeds):
        problems.append(f"row seeds {sorted({p[1] for p in pairs})} differ from manifest seeds {seeds}")

    # 4. crashed graders: evaluator_failures, or a None / NaN value for a graded spec metric
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s): {pr['evaluator_failures'][0]}")
    graded = [m for m in _graded_ids(spec) if any(m in r for r in rows) or any(m in r for r in brows)]
    missing = [(r.get("item_id"), r.get("seed"), m) for r in rows for m in graded
               if r.get(m) is None or _is_bad_number(r.get(m))]
    if missing:
        problems.append(f"{len(missing)} graded value(s) are None/NaN (crashed grader?), first {missing[0]}")

    # 5. reported metrics must follow from the rows (no hand-edited numbers)
    if rows and not missing:
        has_cost = all("cost" in r for r in rows)
        try:
            again = aggregate([{**r, "cost": r.get("cost", 0.0)} for r in rows], graded,
                              k_values=spec.get("pass_k", []))
        except Exception as e:  # noqa: BLE001 -- a report we cannot recompute is not trustworthy
            problems.append(f"cannot recompute metrics from rows: {e}")
            again = {}
        for k, v in again.items():
            if k == "cost_per_success" and not has_cost:
                continue
            got = metrics.get(k)
            if v is None or got is None or _is_bad_number(got) or not isinstance(got, (int, float)):
                continue
            if abs(float(got) - float(v)) > 1e-3:
                problems.append(f"metric {k} = {got} but the rows give {v}")

    # 6. ratchet: thresholds may only get stricter on the same eval-set version
    if base_spec is not None:
        problems += _ratchet(spec, base_spec)

    # 7. slice tags per item must equal the baseline's (no relabelling an item out of a slice)
    pt, bt = _slice_tags(rows), _slice_tags(brows)
    relabelled = sorted(i for i in pt.keys() & bt.keys() if pt[i] != bt[i])
    if relabelled:
        problems.append(f"slice tags differ from baseline on {len(relabelled)} item(s), first {relabelled[0]}")
    uneven = [r for r in rows if set(r.get("slices") or []) != pt.get(r.get("item_id"), set())]
    if uneven:
        problems.append(f"{len(uneven)} row(s) carry slice tags inconsistent with their item")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s.get("metric", "pass_rate")
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"            # an empty slice cannot vouch for anything
        else:
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if "max" in s and val > s["max"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if not keys:
                    verdict = "missing"
                else:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000),
                                                       rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        th = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        lines.append(f"  {sid:<38} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
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
