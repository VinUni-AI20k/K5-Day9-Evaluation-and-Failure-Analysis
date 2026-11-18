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
| Trial | `seeded_regression C-002@11` (và tương đương `swarm C-002@55`), run ID trong report: `E-seeded_regression-20261118-2d27` |
| Triệu chứng | Grader `TrialPass` (`pass_rate`), `RefundAmountCorrect` (`refund_amount_correct`) và `DbFactKept` (`db_fact_kept`) đều **FAIL** (`status resolved != denied`). Câu trả lời `reply` (event 6) nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."` và sổ cái ghi `ledger.refund_vnd = 20000`, `refund_count = 1`, `result.status = "resolved"`, trong khi nhãn chuẩn yêu cầu `status = "denied"`, `refund_vnd = 0`, `refund_count = 0`. |
| Bước sai đầu tiên | **Event 3 (`model_override`):** `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | **Event 1 (`handoff`)** tạo yêu cầu `REQ-C-002` với đúng `allowed_tools: ["lookup_order", "lookup_policy", "compute_compensation"]`. **Event 2 (`investigator`)** truy vấn DB trả về đúng sự thật của đơn `O-202`: `{"visible": true, "reason": "ok", "order": {"order_id": "O-202", "status": "delivered", "delay_days": 2, "shipping_fee_vnd": 20000}}` (trễ 2 ngày < ngưỡng 3 ngày của `SHIP-LATE-03`, chưa đủ điều kiện hoàn). Sang **Event 3 (`model_override`)**, agent tin lời khai `"Đơn giao trễ 5 ngày"` trong ticket và ghi đè `order["delay_days"] = 5`, kéo theo **Event 4 (`quote`)** tính sai `amount_vnd = 20000` và hoàn tiền sai. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11`: sau **Event 1 (`handoff`)** và **Event 2 (`investigator`)** (cùng đọc `delay_days: 2`), **không có sự kiện `model_override`**. Agent giữ nguyên `delay_days = 2` của DB nên **Event 3 (`quote`)** trả về `{"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}` và **Event 4 (`reply`)** từ chối đúng: `"Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."` (`ledger.refund_vnd = 0`, `status = "denied"`). |
| Regression test | `tests/test_lab9_graders.py::test_override_event_breaks_db_fact`, `tests/test_lab9_graders.py::test_wrong_amount_in_ledger`, và `tests/test_lab9_evalset.py::test_trace_case_c002_first_wrong_step`: kiểm tra trực tiếp `investigate("seeded_regression", "C-002", 11)` phát hiện event 3 `model_override` (`DbFactKept` = `False`, `RefundAmountCorrect` = `False`) và pass hoàn toàn trên `investigate("fixed", "C-002", 11)`. |
| Chưa chắc chắn | Trace chỉ ghi lại việc `parsed_delay = 5` đè lên `db_delay = 2` thông qua sự kiện `model_override`; nếu một biến thể lỗi khác (`quiet_override`) cũng lấy `delay_days` từ ticket nhưng cố tình không ghi event `model_override` vào trace, grader mức bước (`DbFactKept`) sẽ không thấy mà phải nhờ grader mức kết quả trên sổ cái (`RefundAmountCorrect` so `ledger.refund_vnd` với `label["refund_vnd"]`) chặn lại. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.

