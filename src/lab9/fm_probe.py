"""M1 evidence: run each single-bug variant on the eval set and list the items it breaks.

    python -m lab9.fm_probe                       # v1, seed 11
    python -m lab9.fm_probe --seeds 11,55

Each probe is `fixed` + exactly one bug switch from lab9.variant_agent, so a broken item can be
blamed on that one failure mode. Traces land in traces/R-probe_<bug>-<claim>-s<seed>.json; the
eval set's provenance.from_trace points at them. Nothing in lab8/ is touched.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from lab8.console import utf8_stdio
from lab9.eval import SPEC, load_spec, run_eval
from lab9.variant_agent import make_shape

PROBES = {"FM-01": "leaky_trace", "FM-02": "ignore_denied", "FM-03": "ticket_trust", "FM-04": "sum_parts",
          "FM-04/round": "round_down", "FM-05": "pre_deducted", "FM-06": "stale_clause",
          "FM-07": "sibling_refund", "FM-08": "misreport"}
COUNTS = ("secret_leak", "approval_bypass")


def probe(spec: dict, seeds: list[int]) -> dict[str, dict[str, list[str]]]:
    from lab8.shapes import SHAPES
    ids = [m["id"] for m in spec["metrics"]]
    out: dict[str, dict[str, list[str]]] = {}
    for fm, bug in PROBES.items():
        name = f"probe_{bug}"
        SHAPES[name] = make_shape(name, {"no_override", bug})
        broken: dict[str, list[str]] = {}
        for r in run_eval(name, spec, seeds)["rows"]:
            why = [m for m in ids if m in r and ((m in COUNTS and r[m]) or (m not in COUNTS and r[m] is False))]
            if why:
                broken.setdefault(r["item_id"], sorted(set(broken.get(r["item_id"], [])) | set(why)))
        out[f"{fm} {bug}"] = broken
    return out


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.fm_probe")
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--seeds", default="11")
    args = ap.parse_args(argv)
    res = probe(load_spec(Path(args.spec)), [int(s) for s in args.seeds.split(",")])
    for name, broken in res.items():
        print(f"{name:<26} breaks {len(broken):>2} item(s)")
        for item, why in sorted(broken.items()):
            print(f"    {item}  {', '.join(why)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
