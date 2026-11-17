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
from lab9.graders import GRADERS

SAFETY_COUNTS = ("secret_leak", "approval_bypass")   # aggregated as counts in lab9.eval.aggregate


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
    rows = pr.get("rows") or []
    base_rows = base.get("rows") or []
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]

    # 1. Metric values must be real numbers (NaN < min and NaN > max are both False).
    for k, v in (pr.get("metrics") or {}).items():
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
            problems.append(f"metric {k} is not a number: {v!r}")
        elif isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (NaN/inf hides a crashed grader)")

    # 2. Row count and (item, seed) coverage: nothing dropped, duplicated or cherry-picked.
    man, bman = pr.get("manifest") or {}, base.get("manifest") or {}
    want = int(man.get("items") or 0) * len(man.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest promises {man.get('items')} items x "
                        f"{len(man.get('seeds') or [])} seeds = {want}")
    if (man.get("items"), sorted(man.get("seeds") or [])) != (bman.get("items"), sorted(bman.get("seeds") or [])):
        problems.append(f"manifest items/seeds {man.get('items')}/{man.get('seeds')} differ from the "
                        f"baseline's {bman.get('items')}/{bman.get('seeds')}")
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    dup = len(keys) - len(set(keys))
    if dup:
        problems.append(f"{dup} duplicated (item, seed) row(s)")
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base_rows}
    if set(keys) != base_keys:
        missing, extra = base_keys - set(keys), set(keys) - base_keys
        problems.append(f"(item, seed) set differs from the baseline: {len(missing)} missing, {len(extra)} extra"
                        + (f", e.g. missing {sorted(missing, key=str)[0]}" if missing else ""))

    # 3. Graders must have run on every row.
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s), first: {pr['evaluator_failures'][0]}")
    for m in graded:
        bad = [r for r in rows if not isinstance(r.get(m), bool)]
        if bad:
            problems.append(f"{len(bad)} row(s) with no boolean {m} (crashed or missing grader), "
                            f"e.g. {bad[0].get('item_id')}@{bad[0].get('seed')}={bad[0].get(m)!r}")

    # 4. Reported metrics must be the ones the rows produce (a hand-edited headline number).
    problems += _metrics_match_rows(pr, graded, spec)

    # 5. Slice tags are a property of the item, fixed by the eval set: same as the baseline's.
    base_slices = {r.get("item_id"): sorted(r.get("slices") or []) for r in base_rows}
    relabelled = sorted({r.get("item_id") for r in rows
                         if r.get("item_id") in base_slices and sorted(r.get("slices") or []) != base_slices[r.get("item_id")]})
    if relabelled:
        problems.append(f"slice tags differ from the baseline's for {', '.join(relabelled[:5])}")

    # 6. Ratchet: on the same eval set a spec may only get stricter.
    if base_spec is not None:
        problems += ratchet_check(spec, base_spec)
    return problems


def _metrics_match_rows(pr: dict, graded: list[str], spec: dict) -> list[str]:
    rows, reported, out = pr.get("rows") or [], pr.get("metrics") or {}, []
    if not rows:
        return ["report has no rows"]
    recomputed: dict[str, float | None] = {}
    for m in graded:
        vals = [r[m] for r in rows if isinstance(r.get(m), bool)]
        if m in SAFETY_COUNTS:
            recomputed[m] = sum(vals)
        else:
            recomputed[m] = round(sum(vals) / len(vals), 4) if vals else None
    by_item: dict[str, list[bool]] = {}
    for r in rows:
        if isinstance(r.get("pass_rate"), bool):
            by_item.setdefault(r["item_id"], []).append(r["pass_rate"])
    if by_item:
        recomputed["pass_5"] = round(sum(all(v) for v in by_item.values()) / len(by_item), 4)
        for k in spec.get("pass_k") or []:
            if min(len(v) for v in by_item.values()) >= k:
                for name, fn in (("pass_at", stats.pass_at_k), ("pass_hat", stats.pass_hat_k)):
                    est = [fn(len(v), sum(v), k) for v in by_item.values()]
                    recomputed[f"{name}_{k}"] = round(sum(est) / len(est), 4)
    for k, want in recomputed.items():
        if k not in reported:
            if k in graded:
                out.append(f"metric {k} missing from the report")
            continue
        got = reported[k]
        if want is None or not isinstance(got, (int, float)) or isinstance(got, bool):
            continue                                     # non-numbers are reported by check 1
        if not math.isfinite(float(got)) or abs(float(got) - float(want)) > 1e-3:
            out.append(f"metric {k} = {got} but the rows give {want} (report edited after the run?)")
    return out


_DIRECTION = {"min": -1, "max": +1, "max_increase": +1}   # -1: lower is looser; +1: higher is looser


def ratchet_check(spec: dict, base_spec: dict) -> list[str]:
    """Same eval set => thresholds may only get stricter. A changed eval-set version needs a new
    baseline, which the eval_set_sha check already enforces, so the ratchet always applies here."""
    out: list[str] = []
    for key in ("eval_set", "labels", "eval_set_version", "seeds"):
        if key in base_spec and spec.get(key) != base_spec.get(key):
            out.append(f"RATCHET spec {key} changed {base_spec.get(key)!r} -> {spec.get(key)!r} in the same PR")
    bb, sb = base_spec.get("bootstrap") or {}, spec.get("bootstrap") or {}
    for key in ("method", "rng"):
        if key in bb and sb.get(key) != bb.get(key):
            out.append(f"RATCHET bootstrap {key} changed {bb.get(key)!r} -> {sb.get(key)!r}")
    if float(sb.get("confidence", 0.95)) > float(bb.get("confidence", 0.95)):
        out.append("RATCHET bootstrap confidence raised: a wider CI blocks fewer regressions")
    if int(sb.get("n_resamples", 1000)) < int(bb.get("n_resamples", 1000)):
        out.append("RATCHET bootstrap n_resamples lowered")
    missing_k = set(base_spec.get("pass_k") or []) - set(spec.get("pass_k") or [])
    if missing_k:
        out.append(f"RATCHET pass_k dropped {sorted(missing_k)}")

    def compare(tag: str, new: dict | None, old: dict, new_th: dict, old_th: dict) -> None:
        if new is None:
            out.append(f"RATCHET {tag} removed")
            return
        if old.get("blocking") and not new.get("blocking"):
            out.append(f"RATCHET {tag} no longer blocking")
        for k, v in old_th.items():
            if k == "no_significant_drop":
                if v and not new_th.get(k):
                    out.append(f"RATCHET {tag} dropped no_significant_drop")
            elif k in _DIRECTION:
                if k not in new_th:
                    out.append(f"RATCHET {tag} dropped threshold {k}")
                elif (float(new_th[k]) - float(v)) * _DIRECTION[k] > 1e-12:
                    out.append(f"RATCHET {tag} {k} loosened {v} -> {new_th[k]}")

    new_metrics = {m["id"]: m for m in spec.get("metrics") or []}
    for m in base_spec.get("metrics") or []:
        n = new_metrics.get(m["id"])
        compare(f"metric {m['id']}", n, m, (n or {}).get("threshold") or {}, m.get("threshold") or {})
        if n is not None and n.get("kind") != m.get("kind"):
            out.append(f"RATCHET metric {m['id']} kind changed {m.get('kind')} -> {n.get('kind')}")
    br, nr = base_spec.get("reliability"), spec.get("reliability")
    if br:
        if not nr:
            out.append("RATCHET reliability section removed")
        else:
            if br.get("blocking") and not nr.get("blocking"):
                out.append("RATCHET reliability no longer blocking")
            if nr.get("metric", "pass_rate") != br.get("metric", "pass_rate"):
                out.append("RATCHET reliability metric changed")
            if int(nr.get("max_newly_unreliable_items", 0)) > int(br.get("max_newly_unreliable_items", 0)):
                out.append(f"RATCHET reliability max_newly_unreliable_items loosened "
                           f"{br.get('max_newly_unreliable_items')} -> {nr.get('max_newly_unreliable_items')}")
    new_slices = {(s.get("name"), s.get("metric")): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        n = new_slices.get((s.get("name"), s.get("metric")))
        compare(f"slice {s.get('name')}/{s.get('metric')}", n, s, n or {}, s)
    return out


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
        name, metric = s["name"], s["metric"]
        sid = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        verdict, note, val = "ok", "", None
        if not a:
            verdict = "missing"                         # an empty slice cannot vouch for anything
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000),
                                                       rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}] n={len(keys)}"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        th = {k: s[k] for k in ("min", "no_significant_drop") if k in s}
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
    if spec.get("reliability"):
        rb, rl = reliability_check(pr, base, spec)
        blocked += rb
        lines += rl
    return blocked, lines


def reliability_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """Item-level pass^k: an item that passed on EVERY seed in the baseline and now fails on any.
    Averages (and the mean pass^5) let a PR fix some items while breaking others; this does not."""
    rel = spec["reliability"]
    metric = rel.get("metric", "pass_rate")

    def solid(rep: dict) -> dict[str, bool]:
        acc: dict[str, bool] = {}
        for r in rep.get("rows") or []:
            acc[r["item_id"]] = acc.get(r["item_id"], True) and r.get(metric) is True
        return acc

    b, p = solid(base), solid(pr)
    newly = sorted(i for i, ok in b.items() if ok and not p.get(i, False))
    limit = int(rel.get("max_newly_unreliable_items", 0))
    bad = len(newly) > limit
    rid = f"reliability:{metric}/newly_unreliable_items"
    label = ("BLOCK" if rel.get("blocking") else "warn") if bad else "ok"
    line = f"  {rid:<34} {len(newly)!s:<8} {json.dumps({'max': limit}):<40} {', '.join(newly[:6]):<36} {label}"
    return ([rid] if bad and rel.get("blocking") else []), [line]


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
