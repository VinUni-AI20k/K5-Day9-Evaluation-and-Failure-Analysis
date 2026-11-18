# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Case: `seeded_regression C-002@11`

Trace (rút gọn):
```
== seeded_regression C-002@11  lab8 grader: FAIL (status resolved != denied)
   1 handoff            {"principal_scope": "owner_order_only", "allowed_tools": ["lookup_order", ...]}
   2 investigator       {"lookup_order": {"visible": true, "order": {"order_id": "O-202", "status": "delivered", "delay_days": 2 ...
   3 model_override     {"delay_days": 5}
   4 quote              {"amount_vnd": 20000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03"]}
   5 refund_history     {"refund_count": 0, "refunded_vnd": 0}
   6 reply              {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."}
-- ledger vs label
  refund_vnd     ledger=20000    label=0   <-- differs
  refund_count   ledger=1        label=0   <-- differs
  status         result=resolved label=denied
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-5fcc` (`src/reports/eval_seeded_regression.json`, eval set `5fccf94acc33`) |
| Triệu chứng | Grader Lab 8 FAIL (`status resolved != denied`); `refund_amount_correct` fail. **Ledger**: 1 row, 20.000đ, trong khi nhãn là 0. Reply #6 "đã hoàn 20.000đ" khớp ledger, nên nhìn reply thì tưởng đúng. |
| Bước sai đầu tiên | **#3 `model_override`** `{"delay_days": 5}`: agent ghi đè số ngày trễ của DB bằng số ngày khách khai trong ticket ("giao trễ 5 ngày"). |
| Vì sao là bước *đầu tiên* | #1 handoff đúng scope (`owner_order_only`, chỉ tool đọc). #2 investigator đọc đúng DB: O-202 trễ 2 ngày, chưa đủ điều kiện hoàn. Mọi bước sau đều là hệ quả của #3: #4 quote 20.000 tính trên 5 ngày, #6 reply báo số đó. |
| Failure mode | **FM-03** ticket_trust |
| Đối chứng | `fixed C-002@11`: không có event `model_override`; #3 là `quote {"amount_vnd": 0, "reason": "no_entitlement"}`; ledger 0, status denied, grader Lab 8 PASS. |
| Regression test | `src/tests/test_lab9_trace_case.py`: `test_seeded_regression_overrides_db_fact` khẳng định event #3 là `model_override` và ledger ≠ nhãn; `test_fixed_keeps_db_fact` khẳng định `fixed` không override và ledger = nhãn = 0. Ở mức eval set, `db_fact_kept` và `refund_amount_correct` bắt được lỗi này trên item E-002. Hai test pass, nghĩa là variant lỗi vẫn bị nhận diện là lỗi, còn `fixed` vẫn sạch. |
| Chưa chắc chắn | MockLLM tất định nên trace không cho biết tần suất lỗi với LLM thật. Trace không phân biệt được lỗi do prompt hay do parser (`parse_delay_days`). Một biến thể `quiet_override` có thể gây đúng lỗi này mà không để lại event #3, khi đó chỉ `refund_amount_correct`/`pass_rate` bắt được, `db_fact_kept` thì không. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
