# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.8 | Có | dùng |
| helpful | 100 | 0.375 | 1.0 | 0.3 | Không (`κ=0.375 < 0.6`, `R=0.3 < 0.7`) | loại |

## ≥5 case audit thủ công (gồm `tone_ok` và `helpful`)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / Sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`): "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người đúng | Xưng "em" + "nha" quá suồng sã. Bổ sung vào rubric `tone_ok`: cấm từ ngữ suồng sã ("nha", "nhé", tự xưng "em/bạn"). |
| 2 | `H-017` (`tone_ok`): "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha." | PASS | FAIL | Người đúng | Dù có "Dạ", vẫn gọi khách là "bạn" và dùng "nha". Rubric cần kiểm tra danh xưng bắt buộc ("anh/chị"). |
| 3 | `H-029` (`tone_ok`): "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người đúng | Giọng ra lệnh ("không cần nhắn thêm"). Rubric cần phạt câu mang tính đuổi/ra lệnh khách hàng. |
| 4 | `H-042` (`tone_ok`): "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người đúng | Judge quá nhạy (FP), có thể do thiếu chữ "LogiX" hoặc "anh/chị". Bổ sung few-shot PASS mẫu cho câu thông báo ngắn gọn nhưng lịch sự. |
| 5 | `H-051` (`tone_ok`): "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người đúng | Judge bắt bẻ từ tiếng Anh "refund" dù giọng điệu lịch sự. Làm rõ trong rubric rằng thuật ngữ phổ thông ("refund") không làm fail tone nếu xưng hô chuẩn. |
| 6 | `HL-015` (`helpful`): "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." | PASS | FAIL | Người đúng | Ledger chỉ ghi 40.000đ (sai tiền). Judge không có ledger nên không thể chấm tính chính xác số tiền — phải tách khỏi judge, chấm bằng code (`reply_matches_ledger`). |
| 7 | `HL-016` (`helpful`): "Dạ, LogiX thành thật xin lỗi... LogiX đã hoàn 55.000đ cho đơn O-404..." | PASS | FAIL | Người đúng | Ledger ghi 35.000đ; câu xin lỗi dài dòng đánh lừa judge chấm PASS. Khẳng định quy tắc: không dùng LLM judge cho tiêu chí có ground-truth số liệu. |

## Kết luận
- **Tiêu chí bị loại:** `helpful` (`κ = 0.375`, `Precision = 1.0`, `Recall = 0.3`, `confusion = {'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`).
- **Lý do (dẫn ma trận nhầm lẫn):** `fn = 21` trên tổng 30 ca FAIL thật khiến Recall chỉ đạt `0.3` và tỉ lệ lỗi quan sát bị đánh giá thấp nghiêm trọng (`observed = 0.09` so với `corrected = 0.30` theo Rogan-Gladen). Nguyên nhân chính là judge chỉ đọc văn bản reply mà không có đối chiếu ledger, nên toàn bộ các ca trả lời lịch sự nhưng sai số tiền (`HL-015`, `HL-016`, `HL-020`, `HL-028`, `HL-035`, `HL-041`, ...) đều lọt qua thành PASS. Do đó **tuyệt đối không dùng `helpful` judge làm gate**; các lỗi liên quan tiền và approval được chuyển sang code grader (`refund_amount_correct`, `reply_matches_ledger`, `approval_bypass`).
- **Tiêu chí được giữ (`tone_ok`):** đạt tất cả ngưỡng tối thiểu (`κ = 0.757 ≥ 0.6`, `P = 0.857 ≥ 0.8`, `R = 0.8 ≥ 0.7`, `observed = 0.28 → corrected = 0.30`), có thể dùng để theo dõi văn phong sau khi cập nhật rubric về xưng hô ("anh/chị") và giọng ra lệnh.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai (`n = 100`); cần nhãn người mới để có tập held-out thật trước khi áp dụng cho model/prompt mới.
