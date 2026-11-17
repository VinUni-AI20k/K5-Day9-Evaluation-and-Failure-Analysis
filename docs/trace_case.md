# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Bảng phân tích chi tiết

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID: `R-seeded_regression-C-002-s11` |
| Triệu chứng | Grader Lab 8 báo `FAIL (status resolved != denied)`; `refund_amount_correct` fail (ledger=20.000đ vs label=0đ); reply nói *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* trong khi đơn không đủ điều kiện bồi thường |
| Bước sai đầu tiên | **Event #3: `model_override`** với payload `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | - Event #1 (`handoff`) đúng: hợp đồng handoff hợp lệ, chỉ giao 3 tool chỉ đọc.<br>- Event #2 (`investigator`) đúng: tool `lookup_order` tra cứu DB trả về `delay_days = 2` (không đủ điều kiện bồi thường theo chính sách `SHIP-LATE-03` cần trễ ≥ 3 ngày).<br>Ngay tại event #3, agent đã tin lời khai của ticket (nói trễ 5 ngày) và đè lên sự thật trong DB. Các bước sau (#4 quote 20.000đ, #5 refund_history, #6 reply) chỉ là hệ quả kéo theo của quyết định sai này |
| Failure mode | **FM-03 (`ticket_trust`)** — tin ticket hơn DB (thuộc layer model/prompt) |
| Đối chứng | Cùng claim `C-002@11` trên shape `fixed`:<br>- Hoàn toàn không có event `model_override`.<br>- Event #3 là `quote` tính trực tiếp từ DB (`amount_vnd: 0`).<br>- Kết quả: status `denied`, ledger `refund_vnd = 0`, trùng khớp 100% với nhãn |
| Regression test | - Test: `test_override_event_breaks_db_fact` và `test_orchestrator_and_student_shapes_resist_t02_seed_55_trap` trong `tests/`.<br>- Grader bắt lỗi: `DbFactKept` (phát hiện event `model_override`), `RefundAmountCorrect` (ledger ≠ 0) và `TrialPass` (status ≠ denied).<br>- Đã xác nhận: test FAIL trên `seeded_regression` và PASS trên `fixed` |
| Chưa chắc chắn | Trace chỉ ghi nhận sự kiện `model_override` nhưng MockLLM không lưu toàn bộ chuỗi suy luận (chain-of-thought) giải thích vì sao model quyết định tin ticket hơn DB |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case hoàn thành với đầy đủ bằng chứng đối chứng giữa phiên bản lỗi và phiên bản đã sửa lỗi.
