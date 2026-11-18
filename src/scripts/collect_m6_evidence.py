"""Generate M6 A/A, reliability controls and public mutation evidence.

From src/: python -m scripts.collect_m6_evidence
Refresh M5 evidence first; reports are generated from trials, never edited.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
import os
from pathlib import Path
import subprocess
import sys

from lab8.console import utf8_stdio
from lab9 import evalset, gate, stats, variants
from lab9.eval import load_spec, per_item, run_eval
from lab9.mutation import EXPECTED
from scripts.collect_m5_evidence import write

SPEC = Path("config/metric_spec_v2.yaml")
ALT_SEEDS = [66, 77, 88, 99, 110]
DOCS = Path(__file__).resolve().parents[2] / "docs"
BEGIN, END = "<!-- M6_V2_BEGIN -->", "<!-- M6_V2_END -->"


def checked(report, spec, seeds):
    expected = {(item["item_id"], seed)
                for item in evalset.load_jsonl(Path(spec["eval_set"])) for seed in seeds}
    pairs = [(row["item_id"], row["seed"]) for row in report["rows"]]
    if (report["evaluator_failures"] or len(pairs) != len(expected) or set(pairs) != expected
            or report["manifest"]["seeds"] != seeds
            or report["manifest"]["eval_set_sha"] != evalset.sha12(Path(spec["eval_set"]))
            or report["manifest"]["metric_spec_version"] != spec["metric_spec_version"]
            or any(value is None or not isfinite(value) for value in report["metrics"].values())):
        raise RuntimeError(f"Incomplete or stale report: {report['run_id']}")
    return report


def reliability(report):
    by_item = {}
    for row in report["rows"]:
        if type(row["pass_rate"]) is not bool:
            raise RuntimeError("Missing trial_pass result")
        by_item.setdefault(row["item_id"], []).append(row["pass_rate"])
    return [{"item_id": item, "n": len(passes), "c": sum(passes),
             **{f"{name}_{k}": fn(len(passes), sum(passes), k)
                for name, fn in (("pass_at", stats.pass_at_k), ("pass_hat", stats.pass_hat_k))
                for k in (1, 3, 5)}} for item, passes in sorted(by_item.items())]


def main():
    utf8_stdio()
    spec = load_spec(SPEC)
    metric = next(m for m in spec["metrics"] if m["id"] == "pass_hat_5")
    floor = metric["threshold"]["min"]
    if not metric["blocking"] or floor < 0.8 or spec["seeds"] != [11, 22, 33, 44, 55]:
        raise RuntimeError("M6 requires blocking pass_hat_5 >= 0.8 and prescribed seeds")
    variants.register()
    sources = [SPEC, Path(spec["eval_set"]), Path(spec["labels"]),
               Path("lab9/stats.py"), Path("lab9/gate.py"), Path("lab9/eval.py"),
               Path("lab9/graders.py"), Path("lab9/variants.py"), Path("lab9/variant_agent.py"),
               Path("scripts/collect_m5_evidence.py"), Path("scripts/collect_m6_evidence.py")]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    now = datetime.now(timezone.utc)
    run_id = f"M6-{now:%Y%m%d}-" + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:12]
    paths = {"swarm": Path("reports/baseline_v2.json"),
             **{name: Path(f"reports/eval_m5_{name}.json") for name in ("fixed", "honest_refactor", "slice_regression")}}
    reports = {name: checked(json.loads(path.read_text(encoding="utf-8")), spec, spec["seeds"])
               for name, path in paths.items()}
    base = reports["swarm"]
    alternate = checked(run_eval("swarm", spec, ALT_SEEDS), spec, ALT_SEEDS)
    write(Path("reports/eval_m6_aa_alt.json"), alternate)
    for name in ("seeded_regression", "flaky_regression"):
        reports[name] = checked(run_eval(name, spec), spec, spec["seeds"])
        paths[name] = Path(f"reports/eval_m6_{name}.json")
        write(paths[name], reports[name])
        print(f"{name}: {reports[name]['metrics']}", flush=True)

    per_item_a, per_item_b = reliability(base), reliability(alternate)
    # Check exact counts as well as rounded metric deltas; do not infer noise=0
    # merely from four-decimal display equality. Different seeds are NOT gate-compared.
    if per_item_a != per_item_b:
        raise RuntimeError("Unexpected nonzero A/A per-item reliability difference")
    aa = {key: {"a": val, "b": alternate["metrics"][key], "delta": alternate["metrics"][key] - val}
          for key, val in base["metrics"].items()}
    if any(row["delta"] != 0 for row in aa.values()):
        raise RuntimeError("Unexpected nonzero A/A delta")
    observed = [sum(row["pass_hat_5"] for row in group) / len(group) for group in (per_item_a, per_item_b)]
    if floor >= min(observed):
        raise RuntimeError("Floor must be below the observed A/A pass^5 band")

    scorecard = []
    for name, report in reports.items():
        blocked, lines = gate.check(report, base, spec)
        want = EXPECTED.get(name, "merge")
        got = "block" if blocked else "merge"
        scorecard.append({"shape": name, "report": str(paths[name]), "run_id": report["run_id"],
                          "expected": want, "actual": got, "exit_code": int(bool(blocked)),
                          "blocked": blocked, "gate_lines": lines, "metrics": report["metrics"]})
        if want != got:
            raise RuntimeError(f"Unexpected gate decision: {name}")
    broken = reports["flaky_regression"]
    if "pass_hat_5" not in next(r for r in scorecard if r["shape"] == "flaky_regression")["blocked"]:
        raise RuntimeError("Flaky regression must be blocked by pass_hat_5")
    controls = {}
    for mid, min_only in (("pass_rate", True), ("pass_rate", False), ("pass_hat_5", True)):
        control = deepcopy(spec)
        control["slices"] = []
        control["metrics"] = [deepcopy(next(m for m in spec["metrics"] if m["id"] == mid))]
        if min_only:
            control["metrics"][0]["threshold"].pop("no_significant_drop", None)
        blocked, lines = gate.check(broken, base, control)
        controls[f"{mid}_{'floor_only' if min_only else 'with_paired_ci'}"] = {"blocked": blocked, "lines": lines}
    if controls["pass_rate_floor_only"]["blocked"] or controls["pass_hat_5_floor_only"]["blocked"] != ["pass_hat_5"]:
        raise RuntimeError("Reliability control failed")
    bs = spec["bootstrap"]
    left, right = per_item(broken, "pass_rate"), per_item(base, "pass_rate")
    keys = sorted(right)
    delta, lo, hi = stats.paired_bootstrap([left[k] for k in keys], [right[k] for k in keys],
        n_resamples=bs["n_resamples"], rng=bs["rng"], confidence=bs["confidence"])
    cli = {}
    for label, args in (("aa", ["--aa", ",".join(map(str, ALT_SEEDS))]),
                        ("scorecard", ["--baseline", str(paths["swarm"])])):
        result = subprocess.run([sys.executable, "-B", "-m", "lab9.mutation", "--spec", str(SPEC), *args],
                                capture_output=True, encoding="utf-8", errors="strict",
                                env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                     "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
        cli[label] = {"command": "python -B -m lab9.mutation --spec " + str(SPEC) + " " + " ".join(args),
                      "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        print(result.stdout, flush=True)
        if result.returncode:
            raise RuntimeError(f"Public CLI failed: {label}, exit={result.returncode}\n{result.stderr}")
    summary = {"run_id": run_id, "manifest": {"generated_at": now.isoformat(), "backend": "MockLLM",
        "items": len(per_item_a), "seeds_a": spec["seeds"], "seeds_b": ALT_SEEDS,
        "eval_set_sha": base["manifest"]["eval_set_sha"], "metric_spec_version": spec["metric_spec_version"],
        "source_sha256": hashes}, "aa": {"metrics": aa, "per_item_a": per_item_a, "per_item_b": per_item_b,
        "report_a": str(paths["swarm"]), "report_b": "reports/eval_m6_aa_alt.json",
        "pass_hat_5_observed_band": [min(observed), max(observed)]},
        "threshold": {"metric": "pass_hat_5", "min": floor, "blocking": True,
                      "margin_below_observed_band": min(observed) - floor,
                      "rationale": "0.85 preserves the existing success floor, meets >=0.8, lies below both A/A observations; validate new backends separately."},
        "scorecard": scorecard, "regressions_killed": sum(r["expected"] == r["actual"] == "block" for r in scorecard),
        "false_alarms": sum(r["expected"] == "merge" and r["actual"] == "block" for r in scorecard),
        "flaky": {"per_item": reliability(broken), "pass_rate_paired_ci": {"delta": delta, "lo": lo, "hi": hi},
                  "controls": controls}, "cli": cli, "passed": True}
    write(Path("reports/m6_noise_validation.json"), summary)
    aa_rows = "\n".join(f"| {mid} | {row['a']} | {row['b']} | {row['delta']:+.4f} |" for mid, row in aa.items())
    gate_rows = "\n".join(f"| {r['shape']} | {r['metrics']['pass_rate']:.4f} | {r['metrics']['pass_hat_5']:.4f} | {r['actual']} | {', '.join(r['blocked']) or '—'} |" for r in scorecard)
    ci_verdict = "chặn" if controls["pass_rate_with_paired_ci"]["blocked"] else "không chặn"
    section = f"""{BEGIN}
## v2 — M6: nhiễu A/A và độ ổn định pass^5

Evidence **{run_id}**, [JSON đầy đủ](../src/reports/m6_noise_validation.json), [hướng dẫn tái lập](m6_noise_and_reliability.md). Spec **{spec['metric_spec_version']}**, eval-set SHA **{base['manifest']['eval_set_sha']}**, {len(per_item_a)} item × 5 seed mỗi bộ; MockLLM, SQLite mới mỗi trial.

`pass@k = 1 − C(n−c,k)/C(n,k)` đo ít nhất một lần thành công; `pass^k = C(c,k)/C(n,k)` đo tất cả k lần thành công, lấy mẫu không hoàn lại. Lấy trung bình ước lượng theo item. Từ chối n<1, c ngoài [0,n], k ngoài [1,n] và đầu vào không nguyên (kể cả bool). Ví dụ n=5,c=4,k=5: pass@5=1 nhưng pass^5=0. Với đúng 5 seed, pass^5 là tỉ lệ item qua cả 5 lần.

A/A dùng A={spec['seeds']} và B={ALT_SEEDS}, cùng agent swarm và cùng item. Mọi Δ=B−A bằng 0; kiểm tra thêm số lần PASS từng item, không chỉ số làm tròn. Không đưa hai bộ seed khác nhau qua gate so PR/baseline.

| Metric | Bộ A | Bộ B | Δ |
|---|---:|---:|---:|
{aa_rows}

Dải pass^5 quan sát chính xác là [{min(observed):.6f}, {max(observed):.6f}] = 25/28 ở cả hai bộ; dải Δ=[0,0]. Sàn blocking **pass_hat_5 ≥ {floor}**, cao hơn yêu cầu 0.8 và tương ứng sàn thành công 0.85 sẵn có. Sàn nằm dưới biên thấp A/A {min(observed) - floor:.6f}, không nằm trong dải nhiễu quan sát. Chọn sau khi đo A/A; giữ nguyên mọi sàn và slice M5. Hai lần A/A không phải CI hay bảo đảm false-alarm rate; khoảng cách này chỉ được kiểm chứng với MockLLM/public set.

| Shape | pass_rate | pass^5 | Gate | Lý do block |
|---|---:|---:|---|---|
{gate_rows}

Public mutation CLI: **3/3 regression bị chặn, 0 false alarm**; baseline so chính nó merge. `flaky_regression` có pass_rate={broken['metrics']['pass_rate']:.4f} vẫn trên 0.85 nhưng pass^5={broken['metrics']['pass_hat_5']:.4f} thấp hơn {floor}. Kiểm soát chỉ sàn pass_rate: không chặn; chỉ pass_hat_5: chặn. Đây là phép tách riêng vai trò metric, không sửa spec production.

Với cấu hình bootstrap hiện tại, riêng pass_rate đầy đủ (có paired CI) **{ci_verdict}** flaky: Δ={delta:+.6f}, CI95%=[{lo:+.6f},{hi:+.6f}]. Full gate còn có các lý do trong bảng; không khẳng định pass_hat_5 là metric duy nhất phát hiện lỗi, hoặc mọi bộ seed đều khiến paired CI bỏ lọt.

LLM thật có biến thiên sinh token, dịch vụ và môi trường tool nên A/A thường có dải nhiễu >0. Cần nhiều cặp A/A trên cùng item, cùng thiết kế seed/ngân sách, bootstrap theo item và quan sát phân vị đuôi thấp trước khi đặt sàn thấp hơn dải dao động chấp nhận được. Giữ ratchet: nếu sàn hiện hành quá sát nhiễu thì tăng seed/cỡ mẫu hoặc đổi phiên bản eval và duyệt baseline mới; không hạ sàn cùng phiên bản để làm PR xanh. MockLLM Δ=0 không chứng minh model thật không nhiễu.

Chỉ 5 seed: bug xác suất 1/5 có xác suất bỏ lỡ (4/5)^5≈32.77%; bug 1/3 có xác suất bỏ lỡ (2/3)^5≈13.17%, nếu các trial độc lập. Seed và công tắc lỗi trong lab là xác định, nên đây là minh họa sampling, không phải xác suất được đo cho seed cố định. Các lỗi tương quan, sự kiện hiếm hoặc chưa có trong public pack vẫn có thể lọt; pass^5 giảm khi chỉ một trial hỏng, nhưng không phát hiện lỗi chưa xuất hiện. Chưa đánh giá hidden variants hay LLM thật. M7 integrity/ratchet vẫn TODO; chưa tuyên bố toàn bộ Advanced/Expert hoặc CI v2 xanh.
{END}
"""
    original = (DOCS / "eval_card.md").read_text(encoding="utf-8")
    if BEGIN in original:
        before, rest = original.split(BEGIN, 1)
        _, after = rest.split(END, 1)
        card = before.rstrip() + "\n\n" + section + after
    else:
        card = original.rstrip() + "\n\n" + section
    (DOCS / "eval_card.md").write_text(card, encoding="utf-8", newline="\n")
    commands = r"""
Trong thư mục `src/`, chạy tuần tự:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -B -m scripts.collect_m5_evidence
.\.venv\Scripts\python.exe -B -m scripts.collect_m6_evidence
.\.venv\Scripts\python.exe -B -m pytest -q -m student -o addopts= -k "lab9 and not integrity"
```

Script M6 chạy cả CLI A/A và mutation scorecard gốc, lưu stdout/exit code vào JSON, cùng per-item n/c, sáu ước lượng pass-k, report của từng shape và mã nguồn SHA256. M5 evidence được refresh bằng spec 2.3; các báo cáo M4/v1 giữ nguyên. Test M7 integrity chưa thuộc phạm vi M6. Các JSON được sinh bởi harness/script, không sửa bằng tay; không thay đổi Lab8, variants, pack hoặc traps.
"""
    (DOCS / "m6_noise_and_reliability.md").write_text(
        "# M6 — A/A và độ ổn định\n\n" + section + commands, encoding="utf-8", newline="\n")
    print(f"{run_id}: PASS, mutation 3/3, false alarms 0; wrote M6 report and docs", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
