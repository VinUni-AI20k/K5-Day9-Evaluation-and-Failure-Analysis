"""Run the checkpoint commands and retain their real output and expected exit codes.

Run from src: python -m scripts.lab9_verify
Reports are produced by their official CLI, not constructed or patched here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from lab8.console import utf8_stdio


def main():
    utf8_stdio()
    spec = "config/metric_spec_v2.yaml"
    base = "reports/baseline_v2.json"
    commands = [
        ("M0 smoke", ["lab9.smoke"], 0),
        ("M1 build", ["lab9.evalset", "--build"], 0),
        ("M1 check", ["lab9.evalset", "--check"], 0),
        ("M5 build/check", ["lab9.evalset", "--v2", "--build"], 0),
        ("M1 trace evidence", ["scripts.lab9_evidence"], 0),
        ("M2 tone", ["lab9.judge", "--csv", "data/eval/judge_tone_public.csv", "--audit", "10"], 0),
        ("M2 helpful rejected", ["lab9.judge", "--csv", "data/eval/judge_helpful_public.csv", "--audit", "5"], 1),
        ("Host contracts", ["pytest", "-q"], 0),
        ("Core tests", ["pytest", "-q", "-m", "student", "-o", "addopts=", "-k", "lab9 and not advanced"], 0),
        ("Advanced tests", ["pytest", "-q", "-m", "student", "-o", "addopts=", "-k", "advanced"], 0),
        ("M3 detection", ["lab9.mutation", "--detect"], 0),
        ("M4 baseline", ["lab9.eval", "--shape", "swarm", "--out", "reports/baseline_v1.json"], 0),
        ("M4 PR swarm", ["lab9.eval", "--shape", "swarm", "--out", "reports/eval_pr.json"], 0),
        ("M4 PR gate", ["lab9.gate", "--pr", "reports/eval_pr.json", "--baseline", "reports/baseline_v1.json"], 0),
        ("M4 baseline sanity", ["lab9.ci_check", "--pr", "reports/eval_pr.json", "--baseline", "reports/baseline_v1.json"], 0),
        ("M4 fixed", ["lab9.eval", "--shape", "fixed"], 0),
        ("M4 fixed gate", ["lab9.gate", "--pr", "reports/eval_fixed.json", "--baseline", "reports/baseline_v1.json"], 0),
        ("M4 regression", ["lab9.eval", "--shape", "seeded_regression"], 0),
        ("M4 regression gate", ["lab9.gate", "--pr", "reports/eval_seeded_regression.json", "--baseline", "reports/baseline_v1.json"], 1),
        ("M5 baseline v2", ["lab9.eval", "--shape", "swarm", "--spec", spec, "--out", base], 0),
        ("M6 alternate seeds", ["lab9.eval", "--shape", "swarm", "--spec", spec, "--seeds", "66,77,88,99,110", "--out", "reports/aa_v2.json"], 0),
        ("M6 A/A", ["lab9.mutation", "--spec", spec, "--aa", "66,77,88,99,110"], 0),
        ("M5-M7 mutation", ["lab9.mutation", "--spec", spec, "--baseline", base], 0),
        ("M7 baseline self gate", ["lab9.gate", "--pr", base, "--baseline", base, "--spec", spec, "--base-spec", spec], 0),
        ("M5 slice report", ["lab9.eval", "--shape", "slice_regression", "--spec", spec, "--out", "reports/eval_slice_regression.json"], 0),
        ("M7 traps", ["lab9.traps", "--pr", "reports/eval_slice_regression.json", "--baseline", base, "--spec", spec], 0),
    ]
    for trap in ("evaluator_errors_as_nan", "dropped_failing_rows", "cherry_picked_seeds", "loosened_spec"):
        args = ["lab9.gate", "--pr", f"reports/traps/{trap}.json", "--baseline", base]
        args += ["--spec", f"reports/traps/{trap}.spec.yaml", "--base-spec", spec] if trap == "loosened_spec" else ["--spec", spec]
        commands.append((f"M7 {trap} gate", args, 1))
    results = []
    for name, args, expected in commands:
        command = [sys.executable, "-m", *args]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                env={**os.environ, "PYTHONUTF8": "1"})
        passed = result.returncode == expected
        if name == "M4 regression gate":
            last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
            passed &= last.startswith("exit 1 — blocked:") and "pass_rate" in last.split(":", 1)[-1]
        results.append({"checkpoint": name, "command": ["python", "-m", *args],
                        "expected_exit": expected, "actual_exit": result.returncode,
                        "passed": passed, "stdout": result.stdout, "stderr": result.stderr})
        print(f"{'PASS' if passed else 'FAIL'} {name}: exit {result.returncode} (expected {expected})", flush=True)
        if not passed:
            print(result.stdout + result.stderr, flush=True)
            break
    output = Path("reports/verification.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    return 0 if len(results) == len(commands) and all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
