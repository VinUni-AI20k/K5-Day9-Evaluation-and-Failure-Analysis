# Trace case: từ trace tới quyết định sai đầu tiên

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, row `E-002@11` trong report `E-seeded_regression-20261118-9bdd` |
| Triệu chứng | `pass_rate` FAIL (`status resolved != denied`), `refund_amount_correct` FAIL, `db_fact_kept` FAIL. Ledger ghi **20.000đ** (refund_count 1), nhãn là **0đ / denied**. Reply "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." khớp ledger nên `reply_matches_ledger` không bắt — lỗi nằm ở quyết định, không ở lời văn. |
| Bước sai đầu tiên | **Event 3 `model_override`** `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng scope (`owner_order_only`, chỉ tool read-only). Event 2 `investigator` đọc đúng đơn O-202 từ DB với `delay_days: 2`. Event 3 thay số đó bằng "5 ngày" khách tự khai trong ticket. Event 4 `quote` tính trên 5 ngày → clause `SHIP-LATE-03` 20.000đ; mọi bước sau chỉ hệ quả. |
| Failure mode | **FM-03 ticket_trust** |
| Đối chứng | `fixed C-002@11`: không có event `model_override`; event 3 `quote` = `{"amount_vnd": 0, "reason": "no_entitlement"}`, status `denied`, ledger 0đ. Baseline `swarm` cũng mắc lỗi này nhưng chỉ ở seed 55 (`seed % 5 == 0`) → `pass_rate` baseline 0.9857. |
| Regression test | `src/tests/test_lab9_trace_case.py`: `test_trace_case_c002_seed11_caught_on_regression` (assert event 3 là `model_override`, `DbFactKept` và `RefundAmountCorrect` cùng FAIL) và `test_trace_case_c002_seed11_clean_on_fixed` (cả hai PASS). Đã chạy: fail đúng trên variant lỗi, pass trên `fixed`. Item E-002 có `provenance.from_trace`. |
| Chưa chắc chắn | Trace không cho thấy *vì sao* model chọn tin ticket (MockLLM chỉ là công tắc); với LLM thật, tỉ lệ override có thể phụ thuộc cách viết ticket chứ không theo seed. Trace cũng không chứng minh mọi override đều sai — chỉ sai khi ticket mâu thuẫn DB. |
