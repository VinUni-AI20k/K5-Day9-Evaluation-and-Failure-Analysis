# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape swarm --claim C-002 --seed 55               # trial fail trong baseline
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11   # cùng lỗi, seed nào cũng bật
python -m lab9.trace_case --shape fixed --claim C-002 --seed 55               # đối chứng
```

## Case: swarm C-002@55 (FM-03 ticket_trust)

| Trường | Nội dung |
|---|---|
| Trial | `swarm C-002@55`, run `E-swarm-20261117-9b89` (`reports/baseline_v1.json`): dòng fail duy nhất của baseline (`pass_rate` 0.9857 = 69/70) |
| Triệu chứng | `pass_rate`, `refund_amount_correct`, `db_fact_kept` đều FAIL. Ledger ghi **20.000đ**, nhãn **0đ**; status `resolved`, nhãn `denied`. Lab 8 grader: `status resolved != denied` |
| Bước sai đầu tiên | **Event 3** `model_override` `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng hợp đồng (`owner_order_only`, 3 tool đọc). Event 2 `investigator` đọc đúng DB: O-202 `delay_days = 2`, đơn của P-100 nên `visible`. Event 3 thay số 2 bằng số 5 lấy từ ticket ("giao trễ 5 ngày"). Event 4 `quote` 20.000đ đúng luật với dữ kiện 5 ngày nên chỉ là hậu quả, không phải nguyên nhân |
| Failure mode | FM-03 ticket_trust (`docs/failure_taxonomy.md`) |
| Đối chứng | `fixed C-002@55`: không có `model_override`; `quote` = 0đ `no_entitlement`, status `denied`, ledger 0đ, grader PASS. Swarm chỉ tin ticket ở seed chia hết cho 5, nên seed 11..44 cũng ra đúng như `fixed` |
| Regression test | `tests/test_lab9_trace_case.py`. `test_lab9_trace_case_ticket_trust_is_caught` chạy `swarm C-002@55` và `seeded_regression C-002@11`, assert event ngay trước `model_override` là `investigator` với `delay_days == 2`, override là `{"delay_days": 5}`, và `DbFactKept` + `RefundAmountCorrect` cùng FAIL. `test_lab9_trace_case_fixed_keeps_db_fact` chạy `fixed` ở seed 11 và 55: không có override, hai grader PASS, status `denied`. Đã thấy fail trên variant lỗi và pass trên `fixed` (4/4 test xanh) |
| Chưa chắc chắn | Trace có event `model_override` vì shape tự ghi nó. Biến thể `quiet_override` (cùng lỗi, không ghi event) làm `DbFactKept` mù; khi đó chỉ còn `RefundAmountCorrect` và slice `denial` bắt được. Trên MockLLM, quyết định tin ticket là luật cứng theo seed, nên trace không cho biết LLM thật sẽ tin ticket với xác suất bao nhiêu |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
