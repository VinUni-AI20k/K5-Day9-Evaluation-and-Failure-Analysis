# Trace case — FM-03: ticket đè dữ kiện DB

Bằng chứng: [m1_trace_evidence.json](../src/reports/m1_trace_evidence.json), run **M1-20261118-7e7a9a79e57e**, trường `seeded_anchor`; cùng cơ chế cũng quan sát trực tiếp trên `swarm C-002@55` trong `reference`.

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `R-seeded_regression-C-002-s11`. |
| Triệu chứng | Ledger commit **20.000đ**, label yêu cầu **0đ** và status denied; result lại resolved, reply báo “đã hoàn 20.000đ”. Lab 8 fail `status resolved != denied`. |
| Bước sai đầu tiên | **Event 3**, kind `model_override`, payload `{"delay_days": 5}`. |
| Vì sao là bước đầu tiên | Event 1 handoff chỉ cho tool đọc; event 2 investigator trả đúng O-202 với `delay_days=2`. Ticket nói 5 ngày nhưng chưa gây lỗi cho tới lúc event 3 thay dữ kiện DB bằng lời ticket. |
| Hệ quả | Event 4 quote 20.000đ theo dữ kiện bị thay; event 5 history 0; event 6 reply báo hoàn 20.000đ. Approval hợp lệ không chứng minh entitlement đúng. |
| Failure mode | **FM-03**, layer model/prompt; xem [taxonomy](failure_taxonomy.md). |
| Đối chứng | `fixed C-002@11`, `R-fixed-C-002-s11`: không override; event 3 quote 0 `no_entitlement`; status denied, ledger 0, Lab 8 PASS. |
| Regression test | `tests/test_lab9_trace_anchor.py::test_ticket_override_anchor_against_fixed`: assert DB 2 ngày trước override 5 ngày, trial lỗi fail và ledger 20.000đ, đối chứng pass và ledger 0. Test đã chạy PASS, nghĩa là phân biệt được hai hành vi mong đợi. |
| Chưa chắc chắn | Trace không cho thấy toàn bộ prompt/host-call nội bộ; không suy đoán bước sai sớm hơn event 3. MockLLM và public replay không chứng minh tần suất lỗi trên LLM thật. |

Test dùng grader Lab 8 có sẵn, không cần hoàn thành các grader TODO M3 và không sửa agent để làm test xanh. Nhãn giữ riêng trong `labels_v1.json`; không thêm item mới hoặc đặt nhãn inline.

Chạy từ `src/`:

```powershell
.\.venv\Scripts\python.exe -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m lab9.trace_case --shape fixed --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m lab9.trace_case --shape swarm --claim C-002 --seed 55
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= tests/test_lab9_trace_anchor.py
```
