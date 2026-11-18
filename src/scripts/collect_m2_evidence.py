"""Generate the M2 replay calibration report; do not modify public CSV labels.

Run from src/: python -m scripts.collect_m2_evidence
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lab8.console import utf8_stdio
from lab9.judge import FLOORS, calibrate


def main() -> int:
    utf8_stdio()
    inputs = {name: Path(f"data/eval/judge_{name}_public.csv") for name in ("tone", "helpful")}
    sources = [*inputs.values(), Path("lab9/stats.py"), Path("lab9/judge.py")]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    now = datetime.now(timezone(timedelta(hours=7)))
    report = {
        "run_id": f"M2-{now:%Y%m%d}-" + hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest()[:12],
        "manifest": {"generated_at": now.isoformat(), "backend": "CSV replay",
                     "positive_class": "FAIL", "source_sha256": hashes},
        "floors": FLOORS,
        "judges": {name: calibrate(path) for name, path in inputs.items()},
    }
    path = Path("reports/m2_judge_calibration.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(report["run_id"])
    for name, result in report["judges"].items():
        print(name, {k: v for k, v in result.items() if k != "disagreements"})
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
