# Trace case: ticket ghi đè sự thật DB

Chạy lại tái hiện:

```powershell
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
```

| Trường | Bằng chứng |
|---|---|
| Trial | `seeded_regression C-002@11`; report variant được sinh bằng `lab9.eval` có run ID riêng. |
| Triệu chứng | Lab 8 grader FAIL: `status resolved != denied`. Label mong refund 0; ledger ghi 20.000 VND, 1 dòng. |
| Bước sai đầu tiên | Event 3 `model_override`: `{"delay_days": 5}`. Ticket nói giao trễ 5 ngày dù dữ liệu order trong DB không cho phép khoản hoàn này. |
| Vì sao là bước đầu tiên | Event 1 handoff chỉ cấp read-only tools; event 2 đọc order và policy. Chỉ tại event 3 agent thay `delay_days` từ dữ liệu đã đọc bằng ticket. Event 4 quote 20.000, sau đó host nhận yêu cầu và ghi tiền. |
| Failure mode | FM-03 `ticket_trust`; đồng thời hậu quả là outcome/ledger sai. |
| Đối chứng | `fixed C-002@11` không có event override; quote 0 (`no_entitlement`), không ghi ledger, reply denied, grader PASS. |
| Regression test | `tests/test_lab9_trace_case.py::test_seeded_regression_denial_and_fixed_counterexample`; kiểm tra variant lỗi và bản fixed. `TrialPass`/`pass_rate` bắt lỗi trạng thái và ledger. |
| Chưa chắc chắn | Trace chứng minh thứ tự sự kiện và ledger của replay này; không chứng minh mọi ticket/model sẽ hành xử như vậy trong production. |

Đầu ra quan sát được: broken có `refund_vnd=20000`, `refund_count=1`; fixed có `refund_vnd=0`, `refund_count=0`. Không sửa trace hay report bằng tay; tái sinh bằng command trên.
