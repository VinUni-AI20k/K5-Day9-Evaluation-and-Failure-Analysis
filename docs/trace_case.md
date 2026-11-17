# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi nhóm 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | seeded_regression C-002@11; report E-seeded_regression-20261117-eb7e |
| Triệu chứng | Lab 8 grader FAIL: status resolved thay vì denied; reply báo hoàn 20.000đ, ledger ghi 20.000đ, nhãn yêu cầu 0đ. |
| Bước sai đầu tiên | Event 3 `model_override`: `{"delay_days": 5}`. |
| Vì sao là bước đầu tiên | Event 1 bàn giao tác vụ; event 2 tra cứu đơn O-202. Dữ liệu đơn ghi trễ 2 ngày; event 3 thay thành 5 ngày theo ticket. |
| Failure mode | FM-03 — ticket_trust. |
| Đối chứng | fixed C-002@11 không có event override; quote 0đ, ledger 0đ và status denied. |
| Regression test | `tests/test_lab9_trace_case.py::test_lab9_c002_ticket_does_not_override_db`: `DbFactKept` và `RefundAmountCorrect` trả False với seeded_regression, True với fixed; 2 test đã chạy đạt. |
| Chưa chắc chắn | Trace cho thấy dữ liệu bị override và hậu quả; riêng trace không chứng minh được quá trình suy luận bên trong model. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
