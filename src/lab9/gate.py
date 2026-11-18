"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from math import isclose, isfinite
from numbers import Real
from pathlib import Path

import yaml

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


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
    problems = []

    def number(value):
        try:
            return isinstance(value, Real) and isfinite(value)
        except (OverflowError, ValueError):
            return False

    def entries(policy, key, identity):
        values = policy.get(key, [])
        if not isinstance(values, list):
            problems.append(f"spec {key} must be a list")
            return {}
        indexed = {}
        for entry in values:
            if not isinstance(entry, dict) or any(not isinstance(entry.get(k), str) or not entry[k] for k in identity):
                problems.append(f"spec {key}: invalid identity")
                continue
            name = tuple(entry[k] for k in identity)
            if name in indexed:
                problems.append(f"spec {key}: duplicate {name}")
            indexed[name] = entry
            th = entry.get("threshold", {}) if key == "metrics" else entry
            if not isinstance(th, dict):
                problems.append(f"spec {key} {name}: invalid threshold")
                continue
            for field in ("min", "max", "max_increase"):
                if field in th and (isinstance(th[field], bool) or not number(th[field])):
                    problems.append(f"spec {key} {name}: non-finite/nonnumeric {field}")
            for field, source in (("blocking", entry), ("no_significant_drop", th)):
                if field in source and not isinstance(source[field], bool):
                    problems.append(f"spec {key} {name}: {field} must be boolean")
        return indexed

    if not isinstance(spec, dict) or (base_spec is not None and not isinstance(base_spec, dict)):
        return ["spec and base_spec must be mappings"]
    policies = [(spec, entries(spec, "metrics", ("id",)), entries(spec, "slices", ("name", "metric")))]
    if base_spec is not None:
        policies.append((base_spec, entries(base_spec, "metrics", ("id",)),
                         entries(base_spec, "slices", ("name", "metric"))))
    if not policies[0][1]:
        problems.append("spec has no metrics")
    if problems:
        return problems
    if base_spec is not None and base_spec.get("eval_set_version") is not None and not spec.get("eval_set_version"):
        problems.append("ratchet: eval_set_version removed")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        for key, position in (("metrics", 1), ("slices", 2)):
            for name, old in policies[1][position].items():
                new = policies[0][position].get(name)
                if new is None:
                    problems.append(f"ratchet {key} {name}: removed")
                    continue
                if old.get("blocking") and not new.get("blocking"):
                    problems.append(f"ratchet {key} {name}: blocking removed")
                before = old.get("threshold", {}) if key == "metrics" else old
                after = new.get("threshold", {}) if key == "metrics" else new
                for field in ("min", "max", "max_increase"):
                    if field in before and (field not in after or (
                            after[field] < before[field] if field == "min" else after[field] > before[field])):
                        problems.append(f"ratchet {key} {name}: {field} loosened or removed")
                if before.get("no_significant_drop") and not after.get("no_significant_drop"):
                    problems.append(f"ratchet {key} {name}: no_significant_drop removed")

    def inspect(report, label, policy):
        start = len(problems)
        if not isinstance(report, dict):
            problems.append(f"{label}: report must be a mapping")
            return None
        manifest, rows, metrics = (report.get(k) for k in ("manifest", "rows", "metrics"))
        if not isinstance(manifest, dict) or not isinstance(rows, list) or not isinstance(metrics, dict):
            problems.append(f"{label}: missing/invalid manifest, rows or metrics")
            return None
        if not isinstance(manifest.get("eval_set_sha"), str) or not manifest["eval_set_sha"]:
            problems.append(f"{label}: missing eval_set_sha")
        items, seeds = manifest.get("items"), manifest.get("seeds")
        if (type(items) is not int or items < 1 or not isinstance(seeds, list) or not seeds
                or any(type(seed) is not int for seed in seeds)):
            problems.append(f"{label}: invalid manifest items/seeds")
            return None
        seed_set = set(seeds)
        declared_seeds = policy.get("seeds")
        if declared_seeds is not None and (
                not isinstance(declared_seeds, list) or any(type(s) is not int for s in declared_seeds)
                or len(set(declared_seeds)) != len(declared_seeds) or set(declared_seeds) != seed_set):
            problems.append(f"{label}: manifest seeds differ from the metric spec")
        if len(seed_set) != len(seeds):
            problems.append(f"{label}: duplicate manifest seeds")
        if len(rows) != items * len(seeds):
            problems.append(f"{label}: row count {len(rows)} != items x seeds ({items * len(seeds)})")
        if not isinstance(report.get("evaluator_failures"), list) or report["evaluator_failures"]:
            problems.append(f"{label}: evaluator_failures is missing, invalid or non-empty")
        for mid, value in metrics.items():
            if not number(value):
                problems.append(f"{label}: metric {mid} is missing/non-finite/nonnumeric")
        graded, derived = set(), set()
        for entry in policy.get("metrics", []):
            mid = entry["id"]
            if mid not in metrics:
                problems.append(f"{label}: missing metric {mid}")
            if mid in {"pass_5", "cost_per_success"} or mid.startswith(("pass_at_", "pass_hat_")):
                derived.add(mid)
            else:
                graded.add(mid)
            if entry.get("threshold", {}).get("no_significant_drop"):
                graded.add(mid)
        graded.update(entry["metric"] for entry in policy.get("slices", []))
        if derived:
            graded.add("pass_rate")
        pairs, tags = set(), {}
        for index, row in enumerate(rows):
            if (not isinstance(row, dict) or not isinstance(row.get("item_id"), str) or not row["item_id"]
                    or type(row.get("seed")) is not int):
                problems.append(f"{label}: invalid row identity at index {index}")
                continue
            item, seed = row["item_id"], row["seed"]
            pair = item, seed
            if pair in pairs:
                problems.append(f"{label}: duplicate (item_id, seed) {pair}")
            pairs.add(pair)
            if seed not in seed_set:
                problems.append(f"{label}: row {pair} uses an undeclared seed")
            slices = row.get("slices", [])
            if (not isinstance(slices, list) or any(not isinstance(tag, str) or not tag for tag in slices)
                    or len(set(slices)) != len(slices)):
                problems.append(f"{label}: invalid slice tags for {pair}")
                continue
            current_tags = frozenset(slices)
            if item in tags and tags[item] != current_tags:
                problems.append(f"{label}: inconsistent slice tags across seeds for {item}")
            tags[item] = current_tags
            for mid in graded:
                if not number(row.get(mid)):
                    problems.append(f"{label}: row {pair} has missing/non-finite grade {mid}")
                elif mid in GRADERS and row[mid] not in (0, 1):
                    problems.append(f"{label}: row {pair} has invalid boolean grade {mid}")
            if "cost" in row or "cost_per_success" in derived:
                if not number(row.get("cost")) or row["cost"] < 0:
                    problems.append(f"{label}: invalid cost for {pair}")
        if len(tags) != items:
            problems.append(f"{label}: distinct item count does not match manifest")
        if pairs != {(item, seed) for item in tags for seed in seed_set}:
            problems.append(f"{label}: rows do not cover the complete item x seed set")
        if len(problems) != start:
            return None
        # Report aggregates must agree with the finite trial grades (four-decimal
        # harness output). This also catches edits to the summary alone.
        for mid in graded & metrics.keys():
            values = [row[mid] for row in rows]
            expected = sum(values) if mid in {"approval_bypass", "secret_leak"} else round(sum(values) / len(values), 4)
            if not isclose(metrics[mid], expected, rel_tol=0, abs_tol=1e-9):
                problems.append(f"{label}: aggregate {mid} disagrees with row grades")
        by_item = {}
        for row in rows:
            by_item.setdefault(row["item_id"], []).append(bool(row.get("pass_rate")))
        for mid in derived:
            if mid == "cost_per_success":
                passed = sum(bool(row.get("pass_rate")) for row in rows)
                expected = round(sum(row["cost"] for row in rows) / passed, 4) if passed else None
            elif mid == "pass_5":
                expected = round(sum(all(values) for values in by_item.values()) / len(by_item), 4)
            else:
                try:
                    k = int(mid.rsplit("_", 1)[1])
                    fn = stats.pass_at_k if mid.startswith("pass_at_") else stats.pass_hat_k
                    expected = round(sum(fn(len(v), sum(v), k) for v in by_item.values()) / len(by_item), 4)
                except ValueError:
                    expected = None
            if expected is None or not isclose(metrics[mid], expected, rel_tol=0, abs_tol=1e-9):
                problems.append(f"{label}: aggregate {mid} disagrees with row grades")
        return pairs, tags, seed_set

    current = inspect(pr, "PR", spec)
    baseline_policy = (base_spec if base_spec is not None
                       and spec.get("eval_set_version") == base_spec.get("eval_set_version") else spec)
    previous = inspect(base, "baseline", baseline_policy)
    if current is not None and previous is not None:
        if current[0] != previous[0] or current[2] != previous[2]:
            problems.append("PR and baseline (item_id, seed) sets differ (cherry-picking)")
        if current[1] != previous[1]:
            problems.append("PR and baseline per-item slice tags differ")
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
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        sid = f"slice:{name}/{metric}"
        current, previous = per_item(pr, metric, name), per_item(base, metric, name)
        value, notes, failed = None, [], False
        if not current or not previous:
            failed = True
            notes.append("MISSING: no graded items in PR or baseline slice")
        elif current.keys() != previous.keys():
            failed = True
            notes.append("MISSING: PR and baseline slice item sets differ")
        elif not all(isfinite(v) for v in [*current.values(), *previous.values()]):
            failed = True
            notes.append("MISSING: non-finite slice values")
        else:
            # Each item has equal weight even if its number of seed rows differs.
            value = sum(current.values()) / len(current)
            if "min" in entry and value < entry["min"]:
                failed = True
                notes.append(f"below floor {entry['min']}")
            if entry.get("no_significant_drop"):
                keys = sorted(current)
                if len(keys) < 2 and current != previous:
                    failed = True
                    notes.append("MISSING: paired CI requires at least two slice items")
                else:
                    delta, low, high = stats.paired_bootstrap(
                        [current[k] for k in keys], [previous[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    notes.append(f"Δ {delta:+.3f} CI [{low:+.3f}, {high:+.3f}]")
                    if high < 0:
                        failed = True
        if failed and entry.get("blocking"):
            blocked.append(sid)
        verdict = "BLOCK" if failed and entry.get("blocking") else "warn" if failed else "ok"
        display = "None" if value is None else f"{value:.4f}"
        lines.append(f"  {sid:<36} {display:<8} items={len(current)} {'; '.join(notes)} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    pm = pr.get("manifest") if isinstance(pr, dict) else None
    bm = base.get("manifest") if isinstance(base, dict) else None
    if (isinstance(pm, dict) and isinstance(bm, dict) and pm.get("eval_set_sha")
            and bm.get("eval_set_sha") and pm["eval_set_sha"] != bm["eval_set_sha"]):
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
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
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
    try:
        pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
        blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"  INTEGRITY cannot read evaluation inputs: {exc}")
        print("exit 1 — blocked: integrity")
        return 1
    pr_id = pr.get("run_id", "<missing>") if isinstance(pr, dict) else "<invalid>"
    base_id = base.get("run_id", "<missing>") if isinstance(base, dict) else "<invalid>"
    manifest = pr.get("manifest") if isinstance(pr, dict) else None
    sha = manifest.get("eval_set_sha", "<missing>") if isinstance(manifest, dict) else "<invalid>"
    print(f"gate: PR {pr_id} vs main {base_id} · eval set {sha}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
