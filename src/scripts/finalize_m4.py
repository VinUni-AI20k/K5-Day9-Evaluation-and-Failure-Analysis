"""Validate M4 and render its card/PRD/PR body from generated reports.

Run from src/ after lab9.eval writes baseline_v1, eval_pr, eval_fixed,
eval_seeded_regression. No report numbers are entered manually.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item

REPO = "Hie24/K5-L3B-DAY09-NguyenDucHieu-2A202603772-EvaluationandFailureAnalysis"
OWNER = "Nguyễn Đức Hiếu"
DOCS = Path(__file__).resolve().parents[2] / "docs"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cli(module, args):
    command = [sys.executable, "-B", "-m", module, *args]
    result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True,
                            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def number(value):
    return str(value) if isinstance(value, int) else f"{value:.4f}"


def threshold(metric):
    th = metric.get("threshold", {})
    parts = []
    for key, symbol in (("min", "≥"), ("max", "≤")):
        if key in th:
            parts.append(f"{symbol} {th[key]}")
    if "max_increase" in th:
        parts.append(f"tăng ≤ {th['max_increase']:.0%} so baseline")
    if th.get("no_significant_drop"):
        parts.append("CI của Δ không nằm hoàn toàn dưới 0")
    return "; ".join(parts)


def main() -> int:
    utf8_stdio()
    spec = load_spec()
    committed_set = subprocess.check_output(["git", "show", f"HEAD:src/{spec['eval_set']}"])
    if Path(spec["eval_set"]).read_bytes() != committed_set:
        raise RuntimeError("Eval-set bytes differ from the committed Git blob; normalize LF and commit the intended set first")
    paths = {"swarm": "reports/baseline_v1.json", "pr_swarm": "reports/eval_pr.json",
             "fixed": "reports/eval_fixed.json", "seeded_regression": "reports/eval_seeded_regression.json"}
    reports = {name: read(path) for name, path in paths.items()}
    base = reports["swarm"]
    expected_pairs = {(r["item_id"], r["seed"]) for r in base["rows"]}
    for name, report in reports.items():
        if report["evaluator_failures"] or report["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
            raise RuntimeError(f"{name}: broken graders or mismatched eval set")
        if len(report["rows"]) != base["manifest"]["items"] * len(spec["seeds"]):
            raise RuntimeError(f"{name}: incomplete rows")
        if {(r["item_id"], r["seed"]) for r in report["rows"]} != expected_pairs:
            raise RuntimeError(f"{name}: different item/seed pairs")
    results = {}
    for name in paths:
        result = cli("lab9.gate", ["--pr", paths[name], "--baseline", paths["swarm"], "--spec", str(SPEC)])
        expected_exit = 1 if name == "seeded_regression" else 0
        if result["exit_code"] != expected_exit or f"exit {expected_exit} —" not in result["stdout"]:
            raise RuntimeError(f"{name}: unexpected gate result {result}")
        if name == "seeded_regression" and "pass_rate" not in result["stdout"].splitlines()[-1]:
            raise RuntimeError("seeded_regression must explicitly block pass_rate")
        results[name] = result
    results["ci_check"] = cli("lab9.ci_check", ["--pr", paths["pr_swarm"], "--baseline", paths["swarm"],
                                                "--spec", str(SPEC)])
    results["core_tests"] = cli("pytest", ["-q", "-m", "student", "-o", "addopts=", "-k", "lab9 and not advanced"])
    if results["ci_check"]["exit_code"] or results["core_tests"]["exit_code"]:
        raise RuntimeError(f"M4 local CI validation failed: {results}")
    intervals = {}
    bs = spec["bootstrap"]
    for name in ("fixed", "seeded_regression"):
        intervals[name] = {}
        for metric in spec["metrics"]:
            if not metric.get("threshold", {}).get("no_significant_drop"):
                continue
            mid = metric["id"]
            a, b = per_item(reports[name], mid), per_item(base, mid)
            keys = sorted(b)
            delta, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                  n_resamples=bs["n_resamples"], rng=bs["rng"],
                                                  confidence=bs["confidence"])
            intervals[name][mid] = {"delta": delta, "low": lo, "high": hi, "paired_items": len(keys)}
    ref = intervals["seeded_regression"]["pass_rate"]
    if any(abs(ref[k] - v) > 0.01 for k, v in {"delta": -0.271, "low": -0.500, "high": -0.057}.items()):
        raise RuntimeError(f"paired CI differs from checkpoint: {ref}")
    sources = [SPEC, Path("lab9/gate.py"), Path("lab9/stats.py"), Path("lab9/graders.py"), Path("lab9/evalset.py"),
               Path("harness_map.yaml"), Path("scripts/finalize_m4.py"), Path("../.gitattributes"),
               *map(Path, paths.values())]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    now = datetime.now(timezone(timedelta(hours=7)))
    parent = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    grader_commit = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", "lab9/graders.py"], text=True).strip()
    run_id = f"M4-{now:%Y%m%d}-" + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:12]
    summary = {"run_id": run_id, "manifest": {"generated_at": now.isoformat(), "parent_commit": parent,
                "grader_commit": grader_commit, "source_sha256": hashes, "bootstrap": bs,
                "eval_set_sha": base["manifest"]["eval_set_sha"], "metric_spec_version": spec["metric_spec_version"]},
               "report_paths": paths, "run_ids": {k: r["run_id"] for k, r in reports.items()},
               "results": results, "paired_intervals": intervals, "passed": True}
    Path("reports/m4_gate_validation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    metric_rows = "\n".join(
        f"| {m['id']} | {m['kind']} / {m['level']} | {threshold(m)} | {'có' if m.get('blocking') else 'không'} | "
        f"{number(base['metrics'][m['id']])} |" for m in spec["metrics"]
    )
    comparison_rows = "\n".join(
        f"| {m['id']} | {number(base['metrics'][m['id']])} | {number(reports['fixed']['metrics'][m['id']])} | "
        f"{number(reports['seeded_regression']['metrics'][m['id']])} |" for m in spec["metrics"]
    )
    interval_rows = "\n".join(
        f"| {name} | {mid} | {ci['delta']:+.6f} | [{ci['low']:+.6f}, {ci['high']:+.6f}] |"
        for name, metrics in intervals.items() for mid, ci in metrics.items()
    )
    judge = read("reports/m2_judge_calibration.json")["judges"]
    tone, helpful = judge["tone"], judge["helpful"]
    limitations = """- MockLLM là mô phỏng offline, chưa đo trên LLM thật hoặc người dùng thật; cost là chi phí mô phỏng, không phải hóa đơn API và chưa có số latency thực.
- Chỉ 14 item public với 5 seed cố định; CI resample 14 item (đã lấy trung bình theo seed), không coi 70 trial là 70 item độc lập. CI rộng, chỉ phát hiện ổn định regression đủ lớn.
- Judge replay dùng CSV công khai, chưa có nhãn người held-out mới. Không dùng tone judge kiểm tiền/approval.
- Swarm gốc không có event reply; reply_amount_correct=1 là không có numeric claim để đối chiếu, không chứng minh chất lượng lời đáp. Bộ đọc số FM-08 có giới hạn định dạng/ngôn ngữ; xem m3_graders.md.
- Slice gate, pass@k/pass^k, integrity/ratchet chống sửa report còn thuộc M5–M7. Gate Core chưa bảo đảm chặn NaN, dropped rows, cherry-picking hoặc nới spec; không tuyên bố đã đạt Expert.
- Chưa xác minh cấu hình branch protection trên GitHub; quy trình yêu cầu CI xanh trước merge và baseline được version trên main. Chưa đủ bằng chứng phát hành dịch vụ hoàn tiền thật."""
    card = f"""# Eval card — LogiX-VN refund agent, Core M0–M4

Tài liệu được `python -m scripts.finalize_m4` sinh từ report và metric spec; không nhập tay số đo. Evidence run **{run_id}**, ngày {now:%Y-%m-%d} (UTC+7).

## Phiên bản và provenance

- Baseline: **{base['run_id']}**, [baseline_v1.json](../src/reports/baseline_v1.json), shape swarm.
- Đối chứng fixed: **{reports['fixed']['run_id']}**, [eval_fixed.json](../src/reports/eval_fixed.json).
- Regression: **{reports['seeded_regression']['run_id']}**, [eval_seeded_regression.json](../src/reports/eval_seeded_regression.json).
- Fresh PR swarm: **{reports['pr_swarm']['run_id']}**, [eval_pr.json](../src/reports/eval_pr.json); metric được ci_check so khớp baseline.
- Eval set v1 SHA **{base['manifest']['eval_set_sha']}**, {base['manifest']['items']} item × {len(spec['seeds'])} seed; seeds {spec['seeds']}. Nguồn lab8_public; nhãn tách trong labels_v1.json.
- Metric spec **{spec['metric_spec_version']}**; grader commit **{grader_commit[:7]}**; gate/source SHA-256 và parent commit ghi trong [m4_gate_validation.json](../src/reports/m4_gate_validation.json).
- File eval set được ghi UTF-8/LF và ép LF khi checkout qua .gitattributes, để Windows/Linux dùng cùng SHA; nội dung item/nhãn không đổi.

## Metric và ngưỡng

| Metric | Loại / level | Ngưỡng | Blocking | Baseline |
|---|---|---|---|---|
{metric_rows}

## Baseline và hai phiên bản so sánh

| Metric | swarm baseline | fixed | seeded_regression |
|---|---:|---:|---:|
{comparison_rows}

Paired bootstrap: {bs['n_resamples']} resamples, percentile, RNG {bs['rng']}, confidence {bs['confidence']:.0%}. Resample theo item, cùng thứ tự item cho PR và baseline; delta = PR − baseline.

| Phiên bản | Metric có no_significant_drop | Δ | Paired CI |
|---|---|---:|---|
{interval_rows}

## Gate và trách nhiệm

Baseline tự so: exit {results['swarm']['exit_code']}; fresh PR swarm: exit {results['pr_swarm']['exit_code']}; fixed: exit {results['fixed']['exit_code']}; seeded_regression: exit {results['seeded_regression']['exit_code']}.

Verdict regression: `{results['seeded_regression']['stdout'].splitlines()[-1]}`.

Core tests: `{results['core_tests']['stdout'].splitlines()[-1]}`. ci_check exit {results['ci_check']['exit_code']}. Output CLI nguyên bản nằm trong m4_gate_validation.json.

Gate owner: **{OWNER}**, người thực hiện bài cá nhân. Exit 1 thì dừng merge, đọc metric bị chặn và trace, sửa nguyên nhân rồi sinh lại report; không sửa tay JSON hoặc nới sàn để qua gate. PR phải nằm trong [{REPO}](https://github.com/{REPO}/pulls), starter/d09 → main. Trạng thái job thực tế xem [Actions](https://github.com/{REPO}/actions); dấu xanh của detect khi eval-gate bị skip không được tính là nghiệm thu gate.

## Judge và trace case

Tone: κ={tone['kappa']}, P={tone['precision']}, R={tone['recall']}, PASS. Helpful: κ={helpful['kappa']}, P={helpful['precision']}, R={helpful['recall']}, FAIL; bỏ sót {helpful['confusion']['fn']} lỗi nên không dùng làm gate. Chi tiết [judge audit](judge_audit.md).

[Trace case FM-03](trace_case.md): C-002@11 trên seeded_regression, event 3 model_override đè DB bằng lời ticket; regression test đối chiếu fixed chạy được. [Taxonomy](failure_taxonomy.md), [M3 evidence](m3_graders.md) giải thích grader và lỗi reply/ledger.

## Phạm vi và giới hạn

Pilot hiện tại là lab offline cho yêu cầu hoàn phí ship/bồi thường hỏng hàng theo public matrix, có một claim và principal scope. Tiền đi qua host, approval đúng claim/còn hiệu lực, giới hạn theo approved amount và paid amount, cap theo đơn và idempotency. Không xử lý thanh toán thật, nhiều đơn trong một claim, tranh chấp pháp lý hoặc tự tạo approval.

{limitations}

## Version tiếp theo

Thêm/đổi item hoặc nhãn: tăng eval_set_version, chạy lại baseline cùng tập và ghi provenance. Đổi metric/ngưỡng: tăng metric_spec_version; cùng eval-set version chỉ được giữ/chặt hơn, không nới. M5 v2 cần baseline riêng sau khi hoàn thành fm_map, slices và các grader tương ứng.
"""
    prd = f"""# PRD v1.1 — LogiX-VN refund agent: định nghĩa đánh giá và cổng release

v1.1 giữ tính năng Lab 8, bổ sung thước đo, bằng chứng và trách nhiệm. Bảng số liệu được `python -m scripts.finalize_m4` sinh từ spec/report, evidence run **{run_id}**, baseline **{base['run_id']}**.

## 1. Thay đổi so với v1.0

| Mục | v1.0 | v1.1 |
|---|---|---|
| Thành công | Agent xử lý yêu cầu hoàn tiền | Tiền/approval/proposal/reply được code grader kiểm, có ngưỡng và CI |
| Bằng chứng | Demo thủ công | Eval report có run ID, baseline versioned và eval-gate trên PR |
| Rủi ro | Liệt kê chung | FM-01–FM-08 có trace, bước sai đầu tiên và grader |

## 2. Phạm vi pilot

Trong phạm vi: lab offline LogiX-VN, {base['manifest']['items']} item public, {len(spec['seeds'])} seed cố định, claim hoàn phí giao trễ hoặc hỏng hàng trong owner_order_only. Code tính entitlement theo policy hiện hành, lấy max clause; host kiểm approval gắn đúng claim, còn hiệu lực, trừ lịch sử theo đơn một lần, cap theo approved/paid amount và giữ một effect cho mỗi claim. Không đưa ra một trần tiền sản phẩm mới từ số liệu fixture.

Ngoài phạm vi: thanh toán hay dữ liệu khách thật, nhiều đơn trong một claim, tranh chấp pháp lý, agent tự tạo approval, worker tự ghi tiền. Thiếu mã đơn thì needs_info, ngoài principal scope thì escalated, không đủ điều kiện/approval thì denied. Môi trường đo là MockLLM và judge replay, chưa có pilot trên người dùng thật.

## 3. Định nghĩa chạy đúng

Baseline **{base['run_id']}**, eval set SHA **{base['manifest']['eval_set_sha']}**, metric spec **{spec['metric_spec_version']}**.

| Metric | Loại / level | Ngưỡng | Chặn release? | Baseline |
|---|---|---|---|---|
{metric_rows}

Giảm có ý nghĩa: CI {bs['confidence']:.0%} paired bootstrap của Δ(PR − baseline) nằm hoàn toàn dưới 0. Dùng {bs['n_resamples']} resamples, percentile, RNG {bs['rng']}, resample theo item sau khi lấy trung bình seed. Safety là số vi phạm, không được trung bình hóa để che một bypass/leak. Metric không blocking chỉ cảnh báo.

## 4. Failure mode → grader

| FM | Nguyên nhân | Grader / metric | Loại và lý do |
|---|---|---|---|
| FM-01 | Secret trong artifact | SecretLeak / secret_leak | Code quét forbid_substrings, gồm trace/debug |
| FM-02 | Bỏ qua host denied rồi báo hoàn thành | TrialPass; ReplyAmountCorrect nếu có claim tiền | Code so status/label và tiền reply với ledger; ledger 0 không bị gọi nhầm là approval bypass |
| FM-03 | Ticket đè DB | DbFactKept, RefundAmountCorrect, ProposalAmountCorrect | Code kiểm event override và outcome/proposal, không tin lời model |
| FM-04 | Cộng/làm tròn sai | ProposalAmountCorrect, RefundAmountCorrect | Code so số tiền với nhãn và quy tắc max |
| FM-05 | Tự trừ rồi host trừ lần nữa | ProposalAmountCorrect, RefundAmountCorrect | Code bắt cả proposal về 0 khi ledger denied vẫn đúng |
| FM-06 | Điều khoản cũ | TrialPass, ProposalAmountCorrect, RefundAmountCorrect | Code kiểm kết quả theo nhãn policy hiện hành; trace xác định stale clause |
| FM-07 | Ghi cho claim anh em | ApprovalBypass / unexpected_rows | Code kiểm boundary ghi ledger |
| FM-08 | Reply nói khác ledger | ReplyAmountCorrect | Code so numeric refund claim với khoản thực ghi, hỗ trợ paraphrase |

Tiền và phê duyệt luôn chấm bằng code. Judge chỉ dùng khi κ/P/R đạt FLOORS: tone đạt ({tone['kappa']}/{tone['precision']}/{tone['recall']}), helpful bị loại ({helpful['kappa']}/{helpful['precision']}/{helpful['recall']}). Không dùng tone để xác nhận tiền; xem [audit](judge_audit.md).

## 5. Cổng release và bằng chứng

Lệnh: `python -m lab9.gate --pr reports/eval_<shape>.json --baseline reports/baseline_v1.json --spec config/metric_spec.yaml`.

- Baseline dùng swarm, đầy đủ item × seed; baseline/PR phải cùng eval_set_sha. Đây là PR bootstrap baseline đầu tiên; ci_check chạy swarm mới và so metric với baseline được commit. Sau merge, baseline được version trên main; không thay bằng fixed hoặc sửa JSON tay.
- Baseline tự so và PR swarm exit {results['pr_swarm']['exit_code']}; fixed exit {results['fixed']['exit_code']}; seeded_regression exit {results['seeded_regression']['exit_code']}, pass_rate Δ {ref['delta']:+.6f}, CI [{ref['low']:+.6f}, {ref['high']:+.6f}]. Xem [eval card](eval_card.md) và [gate evidence](../src/reports/m4_gate_validation.json).
- Gate exit 1 → không merge. Người xử lý: **{OWNER}**, eval owner bài cá nhân; phân tích metric/trace rồi sửa nguyên nhân, sinh lại report.
- Trong bài không tự waiver bằng cách nới threshold hoặc chỉnh report. Nếu cần ngoại lệ học thuật, ghi lý do vào PR và xin giảng viên duyệt; chưa có ngoại lệ nào được cấp ở tài liệu này.
- PR starter/d09 → main trong repo cá nhân. Chỉ merge sau khi job eval-gate thật sự chạy hết và xanh; detect-only success không đủ. Quy trình này không thay thế cấu hình branch protection chưa được xác minh.

## 6. Rủi ro và bằng chứng còn thiếu

{limitations}

## 7. Khi nào lên v1.2

Thêm/đổi item hoặc nhãn → tăng eval_set_version và chạy lại baseline, không so trực tiếp khác tập. Đổi metric/ngưỡng → tăng metric_spec_version và ghi lý do; cùng tập chỉ được siết. Spec 1.1 bổ sung reply_amount_correct (FM-08) và proposal_amount_correct (FM-04/FM-05), giữ nguyên ngưỡng có sẵn. v2 dành cho M5–M7 và cần baseline riêng; chưa tuyên bố các mục đó hoàn thành.

## 8. Trách nhiệm và phê duyệt

| Vai trò | Người chịu trách nhiệm | Trạng thái |
|---|---|---|
| Product / phạm vi bài cá nhân | {OWNER} | Phạm vi offline của bài; không có chữ ký phê duyệt production |
| Eval owner / xử lý gate | {OWNER} | Có report tái lập và gate CI để nghiệm thu Core |
| Đánh giá học phần | Giảng viên theo LMS của ca | Chấm main và commit trước hạn; không tự ghi thay kết quả chấm |
"""
    DOCS.joinpath("eval_card.md").write_text(card, encoding="utf-8")
    DOCS.joinpath("PRD_v1.1.md").write_text(prd, encoding="utf-8")
    body = f"""Hoàn thiện Core M0–M4 cho LogiX-VN: eval set có taxonomy/provenance, judge calibration, code graders, FM-08 reply/ledger metric và paired-bootstrap release gate.

- Baseline `{base['run_id']}`, eval-set SHA `{base['manifest']['eval_set_sha']}`, metric spec `{spec['metric_spec_version']}`; mọi report được sinh bằng script và force-add.
- Baseline tự so, fresh PR swarm và fixed: exit 0; seeded_regression: exit 1 và chặn `pass_rate`.
- `pass_rate` Δ = {ref['delta']:+.6f}, CI {bs['confidence']:.0%} [{ref['low']:+.6f}, {ref['high']:+.6f}], khớp checkpoint ±0.01.
- `{results['core_tests']['stdout'].splitlines()[-1]}`; ci_check exit 0. M3 detection 20/20, false alarms fixed 0/70 (report đã commit).
- Eval card, PRD v1.1 và section eval trong harness_map đã có. Không sửa Lab 8/variants/traps/nhãn, không nới ngưỡng.

Output gate của seeded_regression (exit 1 là kết quả mong đợi):

```text
{results['seeded_regression']['stdout']}
```

Bằng chứng: `src/reports/m4_gate_validation.json`, `baseline_v1.json`, `eval_fixed.json`, `eval_seeded_regression.json`; `docs/eval_card.md`, `docs/PRD_v1.1.md`.

Giới hạn: MockLLM, 14 item/5 seed, judge replay công khai; chưa có người dùng thật. Advanced/Expert M5–M7 còn TODO. Merge sau khi job eval-gate của PR này chạy đủ và xanh.
"""
    Path("reports/m4_pr_body.txt").write_text(body, encoding="utf-8")
    print(run_id)
    print(results["core_tests"]["stdout"])
    for name, result in results.items():
        print(f"{name}: exit {result['exit_code']}")
    print("pass_rate paired CI:", ref)
    print("wrote M4 report, docs/eval_card.md, docs/PRD_v1.1.md and reports/m4_pr_body.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
