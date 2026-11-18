# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case đã phân tích (`seeded_regression C-002@11` vs `fixed C-002@11`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (cùng cơ chế lỗi xuất hiện trên `swarm C-002@55` khi `seed % 5 == 0`) |
| Triệu chứng | `lab8` grader FAIL (`status resolved != denied`); ledger ghi `refund_vnd=20000`, `refund_count=1` trong khi nhãn chuẩn là `0` và `denied`; `reply` báo `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."`. |
| Bước sai đầu tiên | Event `3` (`model_override`): `{"delay_days": 5}` — agent ghi đè `delay_days=2` lấy từ DB bằng con số `5` ngày do khách viết trong ticket. |
| Vì sao là bước *đầu tiên* | Event `1` (`handoff`) tạo yêu cầu `REQ-C-002` đúng chuẩn `owner_order_only`; Event `2` (`investigator`) truy vấn `lookup_order` trả về đúng dữ liệu DB (`O-202`, `status="delivered"`, `delay_days=2`). Chưa có sai lệch nào trước event `3`. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) |
| Đối chứng | Trên `fixed C-002@11`, sau event `2` (`investigator`), không có event `model_override`; event `3` là `quote` trả `amount_vnd=0, reason="no_entitlement"`, event `4` là `reply` từ chối, ledger ghi `refund_vnd=0, refund_count=0`, `status=denied` (`PASS`). |
| Regression test | `test_c002_seeded_regression_fails_at_model_override_and_fixed_passes` trong `src/tests/test_lab9_trace_case.py` (kiểm tra event `3` là `model_override` trên `seeded_regression C-002@11` và `DbFactKept` FAIL; đồng thời `fixed C-002@11` PASS). |
| Chưa chắc chắn | Trace của `MockLLM` không chứa prompt/chain-of-thought đầy đủ giải thích *tại sao* LLM chọn tin ticket; ngoài ra `eval` hiện dùng `MockLLM` nên chưa kiểm chứng được tần suất lỗi trên LLM thật. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
