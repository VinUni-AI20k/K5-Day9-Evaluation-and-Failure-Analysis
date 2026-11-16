"""Gate scorecard (M5-M7). Runs every public variant through YOUR graders + spec + gate and
compares the decision with the expected one. A regression the gate lets through is a survived
mutant; a harmless change it blocks is a false alarm. Both cost points.

    python -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json
    python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110

--aa runs swarm on a second seed set and prints the per-metric difference from the baseline run.
That is the A/A noise floor you use to pick thresholds; it is NOT a gate run (the gate rightly
refuses a report whose (item, seed) set differs from the baseline's).
The instructor runs the same loop with hidden variants and traps.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab9 import gate, variants
from lab9.eval import SPEC, load_spec, run_eval

EXPECTED = {
    "fixed": "merge",
    "honest_refactor": "merge",
    "seeded_regression": "block",
    "slice_regression": "block",
    "flaky_regression": "block",
}


def scorecard(spec: dict, base: dict, base_spec: dict | None) -> list[tuple[str, str, str, list[str]]]:
    variants.register()
    out = []
    for name, want in EXPECTED.items():
        blocked, _ = gate.check(run_eval(name, spec), base, spec, base_spec)
        out.append((name, want, "block" if blocked else "merge", blocked))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lab9.mutation")
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--baseline", default="reports/baseline_v2.json")
    ap.add_argument("--base-spec", help="spec of the baseline commit (ratchet check)")
    ap.add_argument("--aa", help="comma-separated alternate seeds: print the A/A metric deltas")
    args = ap.parse_args(argv)
    spec = load_spec(Path(args.spec))
    variants.register()
    if args.aa:
        a = run_eval("swarm", spec)["metrics"]
        b = run_eval("swarm", spec, [int(x) for x in args.aa.split(",")])["metrics"]
        print(f"{'metric':<22} {'spec seeds':>10} {'alt seeds':>10} {'delta':>8}")
        for k in a:
            if isinstance(a[k], (int, float)) and isinstance(b.get(k), (int, float)):
                print(f"{k:<22} {a[k]:>10} {b[k]:>10} {b[k] - a[k]:>+8.4f}")
        return 0
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    rows = scorecard(spec, base, base_spec)
    for name, want, got, why in rows:
        tag = "ok" if want == got else ("SURVIVED" if want == "block" else "FALSE ALARM")
        print(f"  {name:<20} expect {want:<5} got {got:<5} {tag:<11} {', '.join(why)}")
    killed = sum(w == g == "block" for _, w, g, _ in rows)
    regs = sum(w == "block" for _, w, _, _ in rows)
    fa = sum(w == "merge" and g == "block" for _, w, g, _ in rows)
    print(f"mutation score {killed}/{regs} · false alarms {fa}")
    return 0 if killed == regs and fa == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
