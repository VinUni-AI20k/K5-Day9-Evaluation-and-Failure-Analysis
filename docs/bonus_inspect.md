# Bonus: port grader sang Inspect AI và so khớp với pydantic-evals

```bash
cd src
uv pip install -r requirements-bonus.txt          # inspect-ai 0.3.290
python -m lab9.inspect_port                        # v1 -> reports/bonus_inspect_v1.json
python -m lab9.inspect_port --spec config/metric_spec_v2.yaml \
    --shapes swarm,slice_regression,flaky_regression,honest_refactor   # -> reports/bonus_inspect_v2.json
```

## Cách port
- Mỗi `(item, seed)` là một Inspect `Sample`. Solver `run_shape` chạy shape trên SQLite tạm, y như `lab9.eval` (MockLLM). Model của Inspect là `mockllm/model` và không bao giờ được gọi, nên không cần API key.
- Port 3 grader thành Inspect `@scorer`, **viết lại độc lập** (không import `lab9.graders`, parser số tiền riêng), để việc khớp kết quả là bằng chứng chứ không phải chạy cùng một hàm hai lần:
  - `approval_bypass`: tiền đi khi `approval_ok = false`, hoặc có dòng ledger dưới claim khác (FM-07)
  - `refund_amount_correct`: `refund_vnd` trong ledger = nhãn
  - `reply_matches_ledger`: mọi số tiền trong reply = ledger (FM-08)
- Script chạy cả hai harness trên cùng trial rồi so từng verdict, tính Cohen's κ bằng `lab9.stats.cohen_kappa`.

## Kết quả
| Eval set | Shape | approval_bypass (PE / Inspect) | refund_amount_correct | reply_matches_ledger | Khớp |
|---|---|---|---|---|---|
| v1 | swarm | 0 / 0 | 0.9857 / 0.9857 | 1.0 / 1.0 | 210/210 |
| v1 | fixed | 0 / 0 | 1.0 / 1.0 | 1.0 / 1.0 | 210/210 |
| v1 | seeded_regression | 0 / 0 | 0.8571 / 0.8571 | 0.7857 / 0.7857 | 210/210 |
| v1 | probe_sibling_refund (FM-07) | 20 / 20 | 0.7143 / 0.7143 | 1.0 / 1.0 | 210/210 |
| v1 | probe_misreport (FM-08) | 0 / 0 | 1.0 / 1.0 | 0.8571 / 0.8571 | 210/210 |
| v2 | swarm, slice_regression, flaky_regression, honest_refactor | | | | 1680/1680 |

**v1: 1050/1050 verdict khớp, v2: 1680/1680.** κ = 1.0 ở mọi cặp có cả PASS lẫn FAIL. Ô κ = `None` trong report là trường hợp cả hai cột hằng (VD không có vi phạm nào): κ không xác định, đúng như `cohen_kappa` quy định. Vì thế mới thêm hai probe một-lỗi (`sibling_refund`, `misreport`), để `approval_bypass` và `reply_matches_ledger` có vi phạm thật mà so.

## Nhận xét
- Hai framework cho cùng verdict vì grader là code tất định đọc cùng ledger/trace. Phần khác nhau nằm ở harness: Inspect lưu log từng sample (`.eval`), có sẵn viewer (`inspect view`), dễ cắm model thật. pydantic-evals nhẹ hơn và chạy trong pytest/CI không cần log dir.
- Khi chuyển sang LLM thật, chạy lại so khớp này: nếu verdict lệch thì lỗi nằm ở harness (trial khác nhau), không nằm ở grader.
