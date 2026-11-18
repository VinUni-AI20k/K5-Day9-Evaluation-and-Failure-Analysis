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
| Trial | `seeded_regression C-002@11`, run ID `seeded_regression-C-002-11` |
| Triệu chứng | Grader Lab 8 `trial_pass` và `db_fact_kept` FAIL (status resolved != denied); reply nói "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." trong khi ledger ghi 20.000đ nhưng nhãn kỳ vọng refund_vnd=0, status=denied. |
| Bước sai đầu tiên | Event 3 `model_override` `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` chuẩn bị đúng hợp đồng; Event 2 `investigator` truy vấn `lookup_order` từ DB đúng sự thật (`delay_days: 2`). Đến Event 3, agent tự ý lấy số liệu 5 ngày từ ticket đè lên DB, kéo theo Event 4 `quote` tính sai thành 20.000đ. |
| Failure mode | `FM-03` (ticket_trust — tin ticket hơn DB) |
| Đối chứng | Cùng `C-002@11` trên shape `fixed`: không có event `model_override`; Event 3 tính thẳng ra `amount_vnd: 0` (`no_entitlement`) và từ chối hoàn tiền hợp lệ (`status: denied`). |
| Regression test | Grader `DbFactKept` (kiểm tra không có event `model_override`) và `test_public_single_run_cases` trong `tests/test_public_matrix.py`; FAIL trên `seeded_regression` và PASS trên `fixed`. |
| Chưa chắc chắn | Trace chỉ ghi nhận việc đè giá trị `model_override`, không lưu suy luận chi tiết của LLM về việc tại sao lại tin câu từ trong ticket hơn dữ liệu truy vấn từ DB. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
