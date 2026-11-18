"""Run M7 CLI checks sequentially and generate reviewable integrity evidence.

From src/: python -B -m scripts.collect_m7_evidence
Uses generated M5/M6 reports as historical inputs; never edits them.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from lab8.console import utf8_stdio
from lab9 import gate
from lab9.eval import load_spec
from scripts.collect_m5_evidence import write

SPEC = Path("config/metric_spec_v2.yaml")
BASE = Path("reports/baseline_v2.json")
DOCS = Path(__file__).resolve().parents[2] / "docs"
BEGIN, END = "<!-- M7_V2_BEGIN -->", "<!-- M7_V2_END -->"


def main():
    utf8_stdio()
    spec = load_spec(SPEC)
    base = json.loads(BASE.read_text(encoding="utf-8"))
    now = datetime.now(timezone(timedelta(hours=7)))
    paths = [SPEC, BASE, Path("config/metric_spec.yaml"), Path("reports/baseline_v1.json"),
             Path("reports/m5_slice_validation.json"), Path("reports/m6_noise_validation.json"),
             Path("lab9/gate.py"), Path("lab9/stats.py"), Path("lab9/graders.py"),
             Path("lab9/eval.py"), Path("lab9/traps.py"), Path("lab9/mutation.py"),
             Path("lab9/variants.py"), Path("lab9/variant_agent.py"), Path(spec["eval_set"]),
             Path(spec["labels"]), Path("scripts/collect_m7_evidence.py"), Path("tests/test_lab9_m7.py"),
             Path("tests/test_lab9_gate.py"), Path("tests/test_lab9_m5.py"),
             Path("../.github/workflows/eval-gate.yml")]
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    run_id = f"M7-{now:%Y%m%d}-" + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:12]
    summary = {"run_id": run_id, "manifest": {"generated_at": now.isoformat(), "backend": "MockLLM",
        "eval_set_sha": base["manifest"]["eval_set_sha"], "metric_spec_version": spec["metric_spec_version"],
        "items": base["manifest"]["items"], "seeds": spec["seeds"], "source_sha256": hashes},
        "cli": {}, "public_traps": {}, "additional_probes": {}, "report_decisions": {}}
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}

    def cli(label, module, args, expected=0, integrity=False):
        cmd = [sys.executable, "-B", "-m", module, *map(str, args)]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", env=env)
        record = {"command": subprocess.list2cmdline(["python", "-B", "-m", module, *map(str, args)]),
                  "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        summary["cli"][label] = record
        if (result.returncode != expected or (integrity and (
                "  INTEGRITY " not in result.stdout or "exit 1 — blocked: integrity" not in result.stdout))):
            raise RuntimeError(f"{label}: unexpected exit/verdict\n{result.stdout}\n{result.stderr}")
        print(f"{label}: exit {result.returncode}", flush=True)
        return record

    def gate_cli(label, report_path, policy=SPEC, expected=0, integrity=False):
        return cli(label, "lab9.gate", ["--pr", report_path, "--baseline", BASE,
                   "--spec", policy, "--base-spec", SPEC], expected, integrity)

    # Required checks run as their documented CLI, rather than accepting a Python
    # exception or another failing metric as proof of an integrity verdict.
    cli("tests", "pytest", ["-q", "-m", "student", "-o", "addopts=", "-k", "lab9"])
    cli("smoke", "lab9.smoke", [])
    cli("evalset_v1", "lab9.evalset", ["--check"])
    cli("evalset_v2", "lab9.evalset", ["--v2", "--check"])
    pr_path = Path("reports/eval_m7_swarm.json")
    cli("eval_swarm_v2", "lab9.eval", ["--shape", "swarm", "--spec", SPEC, "--out", pr_path])
    gate_cli("gate_swarm_v2", pr_path)
    gate_cli("gate_baseline_self", BASE)
    for name in ("fixed", "honest_refactor", "slice_regression"):
        path = Path(f"reports/eval_m5_{name}.json")
        report = json.loads(path.read_text(encoding="utf-8"))
        blocked, lines = gate.check(report, base, spec, spec)
        expected = name == "slice_regression"
        if bool(blocked) != expected or "integrity" in blocked:
            raise RuntimeError(f"Unexpected gate decision for historical {name}")
        summary["report_decisions"][name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "blocked": blocked, "gate_lines": lines}
    # Re-evaluate v1 too, so the unchanged Core baseline is checked by the new gate.
    v1_pr = Path("reports/eval_m7_swarm_v1.json")
    cli("eval_swarm_v1", "lab9.eval", ["--shape", "swarm", "--out", v1_pr])
    cli("gate_swarm_v1", "lab9.gate", ["--pr", v1_pr, "--baseline", "reports/baseline_v1.json",
        "--base-spec", "config/metric_spec.yaml"])
    cli("ci_check_v1", "lab9.ci_check", ["--pr", v1_pr, "--baseline", "reports/baseline_v1.json"])
    # Match the workflow's trusted policy source, without changing Git or accessing the network.
    protected = subprocess.run(["git", "show", "main:src/config/metric_spec_v2.yaml"],
                               capture_output=True, encoding="utf-8", env=env)
    if protected.returncode:
        raise RuntimeError("Cannot read local main policy for the workflow parity check")
    protected_path = Path("reports/m7_main_spec_v2.yaml")
    protected_path.write_text(protected.stdout, encoding="utf-8", newline="\n")
    main_commit = subprocess.run(["git", "rev-parse", "main"], capture_output=True, encoding="utf-8", env=env)
    if main_commit.returncode:
        raise RuntimeError("Cannot resolve the local main policy commit")
    summary["policy_reference"] = {"ref": "main", "commit": main_commit.stdout.strip(),
        "metric_spec_version": load_spec(protected_path)["metric_spec_version"],
        "path": str(protected_path), "sha256": hashlib.sha256(protected_path.read_bytes()).hexdigest()}
    cli("gate_against_main_policy", "lab9.gate", ["--pr", pr_path, "--baseline", BASE, "--spec", SPEC,
                                                  "--base-spec", protected_path])
    cli("build_traps", "lab9.traps", ["--pr", "reports/eval_m5_slice_regression.json",
        "--baseline", BASE, "--spec", SPEC])
    for name in ("evaluator_errors_as_nan", "dropped_failing_rows", "cherry_picked_seeds", "loosened_spec"):
        path = Path(f"reports/traps/{name}.json")
        policy = Path("reports/traps/loosened_spec.spec.yaml") if name == "loosened_spec" else SPEC
        record = gate_cli(f"trap_{name}", path, policy, expected=1, integrity=True)
        summary["public_traps"][name] = {"path": str(path), "exit_code": 1,
            "integrity_reasons": [line.strip() for line in record["stdout"].splitlines() if "INTEGRITY" in line]}
    # Beyond the four supplied traps: a duplicate can replace a different row
    # while keeping total length unchanged; a crashed grader can occur on green.
    green = json.loads(Path("reports/eval_m5_fixed.json").read_text(encoding="utf-8"))
    for name in ("duplicate_same_length", "evaluator_failure_on_green", "slice_relabel", "forged_summary"):
        probe = deepcopy(green)
        if name == "duplicate_same_length":
            probe["rows"][1] = deepcopy(probe["rows"][0])
        elif name == "evaluator_failure_on_green":
            probe["evaluator_failures"] = ["a grader crashed although all retained rows are green"]
        elif name == "slice_relabel":
            item_id = next(row["item_id"] for row in probe["rows"] if "money_movement" in row["slices"])
            for row in probe["rows"]:
                if row["item_id"] == item_id:
                    row["slices"] = [tag for tag in row["slices"] if tag != "money_movement"]
        else:
            probe["metrics"]["pass_rate"] = 0.9
        path = Path(f"reports/m7_probes/{name}.json")
        write(path, probe)
        record = gate_cli(f"probe_{name}", path, expected=1, integrity=True)
        summary["additional_probes"][name] = {"path": str(path), "exit_code": 1,
            "integrity_reasons": [line.strip() for line in record["stdout"].splitlines() if "INTEGRITY" in line]}
    mutation = cli("mutation", "lab9.mutation", ["--spec", SPEC, "--baseline", BASE, "--base-spec", protected_path])
    if "mutation score 3/3" not in mutation["stdout"] or "false alarms 0" not in mutation["stdout"]:
        raise RuntimeError("Mutation scorecard did not confirm 3/3 and 0 false alarms")
    aa = cli("aa", "lab9.mutation", ["--spec", SPEC, "--aa", "66,77,88,99,110"])
    deltas = [float(line.split()[-1]) for line in aa["stdout"].splitlines()[1:] if line.strip()]
    if not deltas or any(delta != 0 for delta in deltas):
        raise RuntimeError("A/A CLI did not confirm zero metric deltas")
    summary.update(passed=True, public_traps_blocked=4, additional_probes_blocked=4,
                   mutation_score="3/3", false_alarms=0, aa_deltas=deltas)
    write(Path("reports/m7_integrity_validation.json"), summary)
    trap_rows = "\n".join(f"| {name} | 1 | {entry['integrity_reasons'][0]} |"
                          for name, entry in {**summary["public_traps"], **summary["additional_probes"]}.items())
    section = f"""{BEGIN}
## v2 — M7: integrity và policy ratchet

Evidence **{run_id}**, [JSON đầy đủ](../src/reports/m7_integrity_validation.json). Ngày {now:%Y-%m-%d} UTC+7; MockLLM, spec {spec['metric_spec_version']}, SHA eval-set {base['manifest']['eval_set_sha']}, {base['manifest']['items']} item × {len(spec['seeds'])} seed. Test: `{summary['cli']['tests']['stdout'].strip().splitlines()[-1]}`.

Gate kiểm tra cả PR và baseline trước khi chấm điểm: metric hữu hạn, đủ grade ở từng row; không chấp nhận None/string/NaN/∞; không có evaluator_failures. Manifest items/seeds phải hợp lệ, seeds duy nhất; đủ tích Descartes item × seed, không dòng trùng kể cả khi tổng số dòng không đổi. Hai report phải có cùng cặp (item_id, seed), cùng tag slice cho từng item; tag cũng phải nhất quán giữa các seed. Thứ tự row, seed hoặc tag không ảnh hưởng. Aggregate của metric được chấm và metric dẫn xuất trong spec phải khớp kết quả tính lại từ row, theo quy tắc làm tròn của harness. JSON/metadata lỗi có verdict INTEGRITY, không dùng traceback làm bằng chứng PASS.

Ratchet đối chiếu `--base-spec`: cùng eval_set_version thì không giảm min, tăng max/max_increase, bỏ threshold/metric/slice, bỏ blocking hoặc no_significant_drop. Không dùng tăng metric_spec_version hoặc xóa eval_set_version để lách. Cho phép giữ/siết sàn và thêm kiểm tra. Đổi eval_set_version chỉ mở vòng thiết kế chính sách mới; gate vẫn từ chối so report khác eval_set_sha, cần baseline cùng tập. Không nới bất kỳ sàn M5/M6 nào.

| Trap / probe | CLI exit | Một lý do thực tế |
|---|---:|---|
{trap_rows}

Bốn trap công khai đều có dòng INTEGRITY và `exit 1 — blocked: integrity`. Bốn probe bổ sung được script sinh từ fixed xanh, không sửa tay JSON. `evaluator_errors_as_nan` có thể không tạo NaN trong mọi cấu hình; vẫn bị chặn do grade None. Không dựa vào tên trap/variant để ra quyết định.

Baseline so chính nó, swarm PR mới, fixed và honest_refactor đều qua gate. Scorecard gốc chạy lại từ trial: **3/3 regression bị chặn, 0 false alarm**. A/A mới: mọi Δ=0. Fresh swarm v1 qua gate và ci_check với baseline Core cũ. CLI, stdout/exit code và source/input hashes được lưu trong JSON.

Workflow v2 fetch lịch sử và lấy spec từ commit base của PR bằng `git show`, đưa vào cả gate swarm và mutation. workflow_dispatch dùng spec tại github.sha. CI chạy toàn bộ test LAB09 và yêu cầu từng trap CLI trả exit 1 kèm INTEGRITY; một exception hay một metric khác đỏ không được coi là bằng chứng integrity. Đã chạy kiểm tra tương đương local, kể cả so với spec từ nhánh main local; chưa chạy GitHub Actions từ xa hay kiểm tra branch protection.

Giới hạn: chưa chạy bộ chấm/variant/trap ẩn của giảng viên, không bảo đảm điểm Expert. Duplicate và evaluator_failures trên run xanh đã có test/probe riêng, nhưng gate không xác thực chữ ký trace hoặc nguồn gốc các grade. Kẻ có quyền thay đồng bộ row, aggregate, baseline hoặc grader có thể tạo report nhất quán giả; cần trusted baseline, replay harness trên CI, review thay đổi grader/workflow và bảo vệ nhánh. Spec gốc phải đến từ nguồn tin cậy; tự đưa cùng spec đã nới vào cả --spec và --base-spec không tạo được bảo đảm ratchet. M5/M6 vẫn chỉ là public MockLLM, 28 item và 5 seed; giới hạn sampling của M6 vẫn áp dụng.
{END}
"""
    card_path = DOCS / "eval_card.md"
    card = card_path.read_text(encoding="utf-8")
    if BEGIN in card:
        before, rest = card.split(BEGIN, 1)
        _, after = rest.split(END, 1)
        card = before.rstrip() + "\n\n" + section + after
    else:
        card = card.rstrip() + "\n\n" + section
    old_title = "# Eval card — LogiX-VN refund agent, Core M0–M4"
    if card.startswith(old_title):
        card = card.replace(old_title, "# Eval card — LogiX-VN refund agent, M0–M7\n\n"
            "Các phần Core, M5 và M6 giữ bằng chứng tại từng mốc; trạng thái integrity/ratchet hiện tại nằm ở mục M7 cuối tài liệu.", 1)
    card_path.write_text(card, encoding="utf-8", newline="\n")
    commands = r"""
Trong thư mục `src/`:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\.venv\Scripts\python.exe -B -m scripts.collect_m7_evidence
```

Script chạy tuần tự để hạn chế dùng bộ nhớ. Các report M5/M6 được giữ làm evidence lịch sử; M7 ghi report swarm mới, trap/probe và validation riêng bằng script. `reports/traps/loosened_spec.spec.yaml` được tạo bởi lab9.traps, chỉ dùng đối chứng chống nới ngưỡng. Không sửa Lab8, variants, mutation hoặc traps để qua kiểm tra. Việc push/PR/merge đang được để riêng theo yêu cầu người dùng.
"""
    (DOCS / "m7_integrity_and_ratchet.md").write_text(
        "# M7 — Chống gian lận eval\n\n" + section + commands, encoding="utf-8", newline="\n")
    print(mutation["stdout"], flush=True)
    print(f"{run_id}: PASS, 4/4 public traps + 4/4 probes, mutation 3/3, false alarms 0", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
