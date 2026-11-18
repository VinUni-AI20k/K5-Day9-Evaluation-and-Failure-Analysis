# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Observed fail → Rogan-Gladen | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|
| `tone_ok` (`judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | 0.280 → 0.300 | PASS | **Dùng** (đạt cả 3 sàn) |
| `helpful` (`judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | 0.090 → 0.300 | FAIL (κ < 0.6, R < 0.7) | **Loại** (không dùng làm gate) |

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Nguyên nhân & cách sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`): *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* | `PASS` | `FAIL` | **Người đúng** (FN) | Xưng hô thân mật quá mức ("em/anh", "nha", "check giúp em"), thiếu chuẩn CSKH. Sửa rubric: cấm đại từ thân mật không chuẩn mực và tiếng lóng/Anh-Việt lẫn lộn ("check", "nha"). |
| 2 | `H-017` (`tone_ok`): *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* | `PASS` | `FAIL` | **Người đúng** (FN) | Dùng "bạn ơi" và "rồi nha" thiếu trang trọng. Sửa rubric: yêu cầu xưng hô "anh/chị" và kết thúc câu lịch sự ("ạ") thay vì "nha/nhé". |
| 3 | `H-029` (`tone_ok`): *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* | `PASS` | `FAIL` | **Người đúng** (FN) | Câu văn cộc lốc, mệnh lệnh ("không cần nhắn thêm") dù có chữ "Dạ". Sửa rubric: không chỉ kiểm tra từ khóa "Dạ" mà phải đánh giá thái độ hợp tác/lịch sự. |
| 4 | `H-042` (`tone_ok`): *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* | `FAIL` | `PASS` | **Người đúng** (FP) | Judge bắt lỗi nhầm do câu ngắn gọn, thiếu lời chào/xin lỗi dài. Sửa rubric: câu ngắn gọn nhưng đầy đủ thông tin, đúng xưng hô ("Dạ ... ạ") vẫn đạt `PASS`. |
| 5 | `H-051` (`tone_ok`): *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* | `FAIL` | `PASS` | **Người đúng** (FP) | Judge phạt từ "refund" (tiếng Anh) dù câu vẫn lịch sự ("Dạ ... ạ"). Sửa rubric: làm rõ danh sách từ chuyên ngành chấp nhận được hay bắt buộc thuần Việt. |
| 6 | `HL-016` (`helpful`): *"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của..."* | `PASS` | `FAIL` | **Người đúng** (FN) | Câu chỉ xin lỗi chung chung, không nêu kết quả xử lý (hoàn hay từ chối, bao nhiêu tiền). Sửa rubric: bắt buộc trả lời rõ trạng thái yêu cầu và số tiền (hoặc lý do từ chối), không chấm `PASS` chỉ vì văn phong xin lỗi dài. |
| 7 | `HL-047` (`helpful`): *"Ok bạn, đơn O-515 xử lý rồi nhé."* | `PASS` | `FAIL` | **Người đúng** (FN) | Thiếu thông tin cụ thể ("xử lý rồi" không rõ hoàn bao nhiêu hay từ chối). Sửa rubric: yêu cầu có bằng chứng hành động cụ thể mới đạt `helpful=PASS`. |

## Kết luận
- **Tiêu chí bị loại:** `helpful` (`judge_helpful_public.csv`) bị loại vì **κ = 0.375 (< 0.6)** và **Recall = 0.300 (< 0.7)** trên ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`. Dù `Precision = 1.0`, judge này bỏ sót **21/30 ca lỗi thực tế** (`fn = 21`), dẫn đến `observed_fail_rate = 0.09` thấp giả tạo so với tỉ lệ lỗi thực sau hiệu chỉnh Rogan-Gladen (`0.30`). Nếu dùng làm gate, 70% câu trả lời vô ích/thiếu thông tin sẽ lọt qua CI.
- **Tiêu chí được dùng:** `tone_ok` đạt cả 3 ngưỡng (`κ = 0.757 ≥ 0.6`, `P = 0.857 ≥ 0.8`, `R = 0.800 ≥ 0.7`, `{'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}`).
- **Rủi ro còn lại:** Judge mới chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới trên tập held-out thật để tránh quá khớp khi sửa rubric.
