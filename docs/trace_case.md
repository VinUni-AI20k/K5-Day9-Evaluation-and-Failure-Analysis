# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run_id = see trial.result.run_id |
| Triệu chứng | `lab8_pass=False` (status `resolved` ≠ label `denied`); ledger `refund_vnd=20000` ≠ label `0`; reply "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." trong khi đúng ra phải từ chối |
| Bước sai đầu tiên | Event #3 `model_override {delay_days: 5}` — agent ghi đè `delay_days` từ 2 (DB thực) lên 5 (theo lời claim), khiến điều kiện SHIP-LATE-03 (≥ 3 ngày) trở thành đủ điều kiện hoàn tiền |
| Vì sao là bước *đầu tiên* | Event #1 (handoff) và #2 (investigator) đúng: DB trả `delay_days=2`, agent ghi nhận đúng. Event #3 là nơi agent ưu tiên dữ liệu từ ticket của khách thay vì dữ liệu DB đã xác minh. |
| Failure mode | **FM-03** (`ticket_trust`): agent tin dữ liệu ticket của khách hơn dữ liệu DB đã xác minh — xem `docs/failure_taxonomy.md` |
| Đối chứng | `fixed` shape cùng C-002@11: không có event `model_override`; `delay_days` giữ nguyên 2; grader cho `status=denied`, `refund_vnd=0` → `lab8_pass=True` |
| Regression test | Grader `DbFactKept` phát hiện event `model_override` → `db_fact_kept=False`; `RefundAmountCorrect` phát hiện `ledger refund_vnd=20000` ≠ `label=0` → FAIL. Cả hai đã thấy fail trên `seeded_regression` và pass trên `fixed` trong `pytest tests/test_lab9_graders.py -k ticket_override_regression` |
| Chưa chắc chắn | Trace không cho thấy *vì sao* model tin ticket hơn DB (prompt injection, context window truncation, hay bias trong instruction). Cần thêm log-level debug của LLM call để xác nhận. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
