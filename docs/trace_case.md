# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case: `seeded_regression` C-002@11

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, item E-002, run ID `R-seeded_regression-C-002-s11` trong report `E-seeded_regression-<ngày>-4e52` |
| Triệu chứng | `pass_rate` FAIL (`status resolved != denied`), `refund_amount_correct` FAIL, `db_fact_kept` FAIL. **Ledger trước**: `refund_vnd` 20.000 (label 0), `refund_count` 1 (label 0). Reply "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." khớp ledger, nên đọc reply thôi thì trông như đúng. |
| Bước sai đầu tiên | **Event #3 `model_override`** — `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | #1 `handoff` đúng hợp đồng (`check_applicable_policy`, chỉ tool read-only). #2 `investigator` đọc đúng DB: O-202 `delay_days=2`, `status=delivered`. Đến #3 agent lấy "trễ 5 ngày" từ ticket đè lên DB. Mọi bước sau đều đúng *về mặt cơ học* nhưng dùng dữ kiện sai: #4 `quote` áp SHIP-LATE-03 (cần ≥3 ngày) ra 20.000đ, host ghi tiền vì approval A-002 hợp lệ tới 20.000đ. |
| Failure mode | **FM-03 ticket_trust** (`docs/failure_taxonomy.md`) |
| Đối chứng | `fixed` C-002@11: không có `model_override`; #3 `quote` = `{"amount_vnd": 0, "reason": "no_entitlement"}` → `denied`, ledger 0, lab8 PASS. Baseline `swarm` cũng mắc đúng lỗi này ở C-002@55 (nhánh `seed % 5 == 0` của swarm_reference tin ticket). |
| Regression test | `src/tests/test_lab9_trace_case.py`: `test_trace_case_c002_first_wrong_step_is_model_override` khẳng định event ngay trước `model_override` là `investigator`, override mang `delay_days=5`, và `DbFactKept` + `RefundAmountCorrect` gắn cờ. `test_trace_case_c002_fixed_keeps_db_fact` khẳng định trên `fixed` cả ba grader (`DbFactKept`, `RefundAmountCorrect`, `ReplyMatchesLedger`) đều sạch. Đã chạy: fail đúng chỗ trên variant lỗi, pass trên `fixed` (chạy trong `pytest -k "lab9 and not advanced"`, nên CI cũng chạy). |
| Chưa chắc chắn | Trace không cho biết *vì sao* agent tin ticket (MockLLM chỉ bật công tắc). Với model thật, cần xem prompt/ngữ cảnh lúc parse. Biến thể `quiet_override` cho thấy cùng lỗi này có thể **không để lại event** `model_override`: khi đó `db_fact_kept` mù, chỉ `refund_amount_correct` (ledger) bắt được. Vì vậy metric tiền phải là metric blocking, còn metric bước chỉ để chẩn đoán. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
