# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (FAIL là lớp dương).

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không (κ, R) | loại |

Confusion: tone `tp 24, fp 4, fn 6, tn 66`; helpful `tp 9, fp 0, fn 21, tn 70`.
Tỉ lệ fail sau hiệu chỉnh Rogan-Gladen: tone 0.28 → 0.30; helpful 0.09 → 0.30.

## Audit thủ công (tone, 6 case)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em/anh" suồng sã, không có số tiền, không có mã đơn. Rubric: bắt buộc xưng "LogiX – anh/chị". |
| 2 | H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người | Có "Dạ" nhưng câu "không cần nhắn thêm" là cụt. Rubric: chữ "Dạ" mở đầu không đủ để chấm lịch sự. |
| 3 | H-070 "…đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Emoji cười trong tin xin lỗi về hoàn tiền. Rubric: cấm emoji. |
| 4 | H-094 "Da, LogiX da hoan 40.000đ…" (không dấu) | PASS | FAIL | Người | Tiếng Việt không dấu. Rubric: yêu cầu có dấu. |
| 5 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng lịch sự, đủ thông tin; judge phạt nhầm vì câu ngắn. Rubric: ngắn không có nghĩa là cụt. |
| 6 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | Một từ tiếng Anh thông dụng không làm hỏng giọng điệu. Rubric: chỉ phạt khi pha tiếng Anh làm khách khó hiểu. |

## Kết luận
- **tone_ok dùng được** làm metric theo dõi. 6/10 bất đồng là judge bỏ sót lỗi về xưng hô, emoji hoặc tiếng Việt không dấu; 4/10 là judge phạt câu ngắn. Đã nêu cách sửa rubric ở bảng trên.
- **helpful bị loại.** Judge chỉ bắt được 9/30 câu không hữu ích (R = 0.30). Trong 21 câu bỏ sót có 18 câu **sai tiền** (reply nói 55.000đ trong khi ledger ghi 40.000đ…) và 3 câu sai xưng hô. Judge không nhìn thấy ledger, và các câu dài nhiều lời xin lỗi (HL-016, HL-043…) lừa được judge. Nếu dùng làm gate, khoảng 70% lỗi sẽ lọt. Phần đúng/sai tiền đã chuyển sang grader code `reply_amount_matches` (FM-08).
- Rủi ro còn lại: judge chỉ được kiểm trên CSV replay đã công khai. Cần thêm nhãn người trên dữ liệu mới để có tập held-out thật.
