"""M0: environment check in < 10 s. python -m lab9.smoke"""
from __future__ import annotations
import importlib, sys
from pathlib import Path

from lab8.config_loader import repo_path


def main() -> int:
    ok = True
    for mod in ("pydantic_evals", "scipy", "numpy", "yaml", "lab8.benchmark"):
        try:
            importlib.import_module(mod); print(f"ok   import {mod}")
        except Exception as e:  # noqa: BLE001
            ok = False; print(f"FAIL import {mod}: {e}")
    paths = (repo_path("data", "public_claims.jsonl"), Path("config/metric_spec.yaml"),
             Path("data/eval/judge_tone_public.csv"))
    for path in paths:
        exists = path.is_file(); ok &= exists; print(f"{'ok  ' if exists else 'FAIL'} file {path}")
    print("M0 PASS" if ok else "M0 FAIL (run from src/)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
