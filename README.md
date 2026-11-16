# K5 · Day 9 · Lab — Evaluation & Failure Analysis (LogiX-VN)

> Nối tiếp Lab 8. Lab 8 trả lời "agent có chạy không"; Lab 9 trả lời **"làm sao biết bản mới tốt hơn — và chặn được bản tệ trước khi merge"**.
> Không cần API key: MockLLM + judge replay. **Không Langfuse / OTel** (observability học ở Day 14).

## Bạn sẽ làm gì (13:30–17:00)
| M | Giờ | Việc | Lệnh kiểm tra |
|---|---|---|---|
| M0 | 13:30 | Overlay starter lên repo Lab 8, cài đặt và sinh eval set | `python -m lab9.smoke` và `python -m lab9.evalset --build` |
| M1 | 13:45 | Taxonomy ≥5 failure mode từ trace; gắn `failure_modes` cho eval set | `python -m lab9.evalset --check` |
| M2 | 14:30 | Judge-the-judge: cài `kappa`, P/R, Rogan-Gladen; audit ≥5 bất đồng | `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5` |
| M3 | 15:15 | Trajectory assertion: `ApprovalBypass`, `RefundAmountCorrect` + 1 metric cho FM-08 | `python -m pytest -q -m student -o addopts= -k lab9` |
| M4 | 16:00 | Paired bootstrap + CI gate: chặn `seeded_regression`, cho qua `fixed` | `python -m lab9.gate ...` (exit 1 / exit 0) |
| — | 16:45 | Eval card + PRD v1.1, nộp | xem `SUBMISSION.md` |

## Cài đặt (M0): chép overlay vào repo Lab 8

Starter này **không chạy độc lập**: nó chỉ có `src/lab9/`, docs và workflow. Code agent, dữ liệu và `requirements.txt` nằm trong repo Lab 8 của nhóm.

**Không cần hoàn thiện Lab 8.** M0–M4 (baseline, gate, `fixed`, `seeded_regression`) đều chạy trên shape `swarm`, tức `lab8/shapes/swarm_reference.py` do giảng viên cung cấp, không dùng `workflow`/`single`/`orchestrator` của nhóm. Repo Lab 8 còn TODO vẫn làm được Lab 9, miễn là package `src/lab8/` còn nguyên.

**Lab 8 bị khóa, trace cố định.** Không sửa file nào trong `src/lab8/` (trừ 10 điểm). Trace không commit sẵn: `lab9.eval` chạy lại agent bằng MockLLM trên 14 item × 5 seed cố định, nên chạy lần nào cũng ra cùng một trace. Việc của bạn là eval và phân tích dựa trên trace đó: taxonomy, judge calibration, grader, bootstrap gate.

```bash
# 1. Ở thư mục chứa repo Lab 8 của nhóm (bản nào cũng được, kể cả chưa xong)
git clone https://github.com/VinUni-AI20k/K5-Day9-Evaluation-and-Failure-Analysis lab9-starter
cd <repo-lab8-cua-nhom>
git switch -c starter/d09

# 2. Chép đúng 3 thư mục. KHÔNG chép README/CHECKPOINTS/RUBRIC/SUBMISSION/.gitignore ở gốc:
#    các file đó trùng tên với Lab 8; đọc chúng ngay trong lab9-starter.
#    Chép nhầm .gitignore sẽ mất dòng chặn .env và src/eval/instructor/ của Lab 8.
cp -R ../lab9-starter/src/. src/
cp -R ../lab9-starter/docs/. docs/
cp -R ../lab9-starter/.github/. .github/     # thêm eval-gate.yml, giữ ci.yml của Lab 8

# 3. Cài và kiểm tra (Python ≥ 3.11; dùng venv hoặc `uv venv && uv pip install ...`)
cd src
python -m pip install -r requirements.txt -r requirements-lab9.txt
python -m lab9.smoke
python -m lab9.evalset --build          # sinh eval_set_v1.jsonl + labels_v1.json (nhãn TÁCH khỏi item)
cd .. && git add -A && git commit -m "chore: add lab9 overlay"
```

Kiểm tra nhanh sau bước 2: `git status` chỉ hiện file **mới** trong `src/lab9/`, `src/tests/test_lab9_*`, `src/config/`, `src/data/eval/`, `docs/` và `.github/workflows/eval-gate.yml`. Nếu thấy file `src/lab8/` bị sửa, bạn đã chép nhầm: `git restore src/lab8`.

**Baseline cho CI (M4).** Job `eval-gate` đọc `src/reports/baseline_v1.json` trên nhánh, nên file này phải được commit. Sinh từ `main` đã hoàn thành M1–M3 (`-f` để chắc chắn không bị `.gitignore` bỏ qua):
```bash
cd src
python -m lab9.eval --shape swarm --spec config/metric_spec.yaml --out reports/baseline_v1.json
git add -f reports/baseline_v1.json && git commit -m "chore: add eval baseline v1"
```
Workflow chạy khi mở PR (hoặc chạy tay ở tab Actions), không chạy khi push thẳng lên `main`.

Ở M0, cả hai lệnh trả exit 0. Các item mới có `failure_modes` rỗng. Sau khi gắn mã lỗi từ taxonomy ở M1, chạy `python -m lab9.evalset --check` và kiểm tra kết quả có 0 lỗi.

Job `eval-gate` cần các bài tập đã hoàn thành và baseline M4. Job chạy test học viên, kiểm tra eval set, rồi dùng cùng metric spec và baseline để chấm `swarm` của PR và xác nhận `fixed` qua gate, `seeded_regression` bị chặn ở `pass_rate`.

## Công nghệ (kiểm tra 11/2026)
- **pydantic-evals 2.68** — harness chính: `Dataset` / `Case` / `Evaluator`, chạy offline, không cần OTel (ta không dùng span evaluator).
- **scipy.stats.bootstrap(paired=True)** — CI cho hiệu hai phiên bản trên cùng item.
- Judge calibration theo thực hành hiện hành: nhãn nhị phân PASS/FAIL, κ ≥ 0.6, P ≥ 0.8, R ≥ 0.7, κ không xác định ⇒ FAIL, hiệu chỉnh tỉ lệ lỗi bằng Rogan-Gladen.
- Bonus (không bắt buộc): port 3 grader sang **Inspect AI** hoặc **DeepEval** và so kết quả.

## Bản đồ file
```
src/lab9/evalset.py   eval set v1 + provenance + check        (TODO M1: failure_modes)
src/lab9/graders.py   pydantic-evals Evaluators               (TODO M3: 2 grader)
src/lab9/stats.py     confusion, P/R, kappa, RG, bootstrap    (TODO M2, M4)
src/lab9/trace_case.py trace → bước sai đầu tiên cho 1 claim@seed (docs/trace_case.md)
src/lab9/judge.py     calibrate judge từ CSV (replay)
src/lab9/eval.py      chạy 1 shape → reports/eval_<shape>.json có run_id
src/lab9/gate.py      PR vs baseline theo metric_spec → exit 0/1
src/lab9/variants.py  fixed / seeded_regression để thử gate
src/config/metric_spec.yaml   ngưỡng (ratchet: cùng eval-set version chỉ được chặt hơn)
```
Quy tắc: không sửa file `lab8/`; không sửa tay `reports/`; không đặt nhãn inline trong item.
