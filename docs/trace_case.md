# Trace case: từ trace tới quyết định sai đầu tiên

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Case: `seeded_regression C-002@11`

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, report `E-seeded_regression-20261118-8282` |
| Triệu chứng | Grader Lab 8 FAIL (`status resolved != denied`). Ledger ghi 20.000đ, `refund_count` 1; nhãn là 0 / 0. Reply "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." nghe hợp lý và khớp ledger, nên chỉ đọc reply thì không thấy lỗi. |
| Bước sai đầu tiên | Event **3** `model_override` `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng task và tool. Event 2 `investigator` đọc đúng đơn O-202 từ DB: `delivered`, `delay_days` = 2, chưa đủ điều kiện hoàn. Đến event 3, agent thay số 2 bằng số 5 lấy từ ticket ("giao trễ 5 ngày"). Event 4 `quote` tính lại trên dữ liệu đã bị đè nên ra 20.000đ; bước này đúng logic, chỉ sai đầu vào. |
| Failure mode | FM-03 ticket_trust |
| Đối chứng | `fixed C-002@11` không có event `model_override`: `quote` ra `0 / no_entitlement`, status `denied`, ledger 0, reply "chưa đủ điều kiện hoàn". Baseline `swarm` cũng mắc lỗi này, nhưng chỉ ở seed 55 (`seed % 5 == 0`). |
| Regression test | `tests/test_lab9_regressions.py::test_trace_case_c002_ticket_trust`: chạy lại trial, kiểm event thứ 3 là `model_override`, `DbFactKept` và `RefundAmountCorrect` cùng FAIL trên `seeded_regression` và cùng PASS trên `fixed`. Test này xanh và nằm trong job CI (`-k "lab9 and not advanced"`). |
| Chưa chắc chắn | Trace không cho biết agent tin ticket vì nội dung ticket hay vì seed. Với MockLLM thì đó là công tắc `ticket_trust`; với LLM thật thì cần thêm các ticket nói dối kiểu khác (đã có trong pack v2: C-101, C-102). |
