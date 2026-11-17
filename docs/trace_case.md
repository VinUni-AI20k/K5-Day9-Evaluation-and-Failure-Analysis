# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Mẫu điền (Case C-002@11)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261117-0917` |
| Triệu chứng | Grader Lab 8 fail (`status resolved != denied`). Sổ cái ghi hoàn 20.000đ (1 lần) trong khi nhãn kỳ vọng 0đ. Reply báo *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* |
| Bước sai đầu tiên | **Event số 3**: `model_override` payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Bước 1 (`handoff`) và Bước 2 (`investigator`) hoàn toàn đúng: tool `lookup_order` đọc chính xác từ DB đơn O-202 có `status: delivered` và `delay_days: 0`. Ngay tại bước 3, agent tin lời ticket ("giao trễ 5 ngày") và ghi đè delay thành 5 ngày. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) |
| Đối chứng | Trên shape `fixed` cùng `C-002@11`: Không có event `model_override`, `quote` tính ra 0đ (`no_entitlement`), status ra `denied` và ledger ghi 0đ (khớp 100% với nhãn). |
| Regression test | `DbFactKept` (kiểm tra không có event `model_override`) và `RefundAmountCorrect` (bắt số tiền ledger 20.000đ != 0đ); test `test_override_event_breaks_db_fact` trong `src/tests/test_lab9_graders.py`. |
| Chưa chắc chắn | Trace chỉ ghi nhận hành vi override, không chứng minh được MockLLM parse câu từ như thế nào nếu prompt bị xáo trộn vị trí từ ngữ. |

## Quy tắc
- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
