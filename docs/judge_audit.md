# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.8 | Đạt (`PASS floors`, observed fail 0.28 → RG 0.30) | dùng |
| helpful | 100 | 0.375 | 1.0 | 0.3 | Không đạt (`FAIL floors`: κ < 0.6, R < 0.7; observed fail 0.09 → RG 0.30) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / Sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | `PASS` | `FAIL` | Người đúng | Câu *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* dùng văn phong thân mật quá mức ("nha", "check giúp em"), không chuẩn mực CSKH LogiX. Bổ sung vào rubric `tone_ok`: cấm từ ngữ suồng sã ("nha", "nhé", "check"). |
| 2 | `H-017` (`tone_ok`) | `PASS` | `FAIL` | Người đúng | *"Dạ, bạn ơi LogiX đã hoàn 25.000đ..."* gọi khách là "bạn ơi" + "rồi nha". Cập nhật rubric `tone_ok`: bắt buộc xưng hô "anh/chị" hoặc "quý khách". |
| 3 | `H-029` (`tone_ok`) | `PASS` | `FAIL` | Người đúng | *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* mang giọng điệu gắt/đóng hội thoại thô. Bổ sung vào rubric: cấm câu mệnh lệnh đuổi/chặn khách hàng. |
| 4 | `H-042` (`tone_ok`) | `PASS` | `PASS` (Judge: `FAIL`) | Người đúng | *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* lịch sự và rõ ràng; judge báo nhầm `FAIL` do thiếu chủ ngữ. Làm rõ rubric `tone_ok`: câu ngắn gọn có "Dạ/... ạ" vẫn hợp lệ. |
| 5 | `H-051` (`tone_ok`) | `PASS` | `PASS` (Judge: `FAIL`) | Người đúng | *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* bị judge bắt lỗi từ tiếng Anh "refund". Sửa rubric: cho phép thuật ngữ chuyên môn phổ thông ("refund") nếu ngữ điệu lịch sự. |
| 6 | `HL-016` (`helpful`) | `PASS` | `FAIL` | Người đúng | *"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của..."* chỉ xin lỗi chung chung, không nêu hướng xử lý/kết quả/bước tiếp theo. Sửa rubric `helpful`: bắt buộc có hành động cụ thể hoặc kết quả/lý do rõ ràng, không chấm `PASS` cho câu xin lỗi sáo rỗng (length bias). |
| 7 | `HL-015` (`helpful`) | `PASS` | `FAIL` | Người đúng | *"Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ."* — reply tự tin nhưng sai/thiếu thông tin cần thiết so với ngữ cảnh yêu cầu. Rubric `helpful` cần đối chiếu đủ điều kiện giải quyết vấn đề chứ không chỉ nhìn cấu trúc câu. |

## Kết luận
- **Tiêu chí bị loại:** `helpful` (`κ = 0.375`, `Precision = 1.0`, `Recall = 0.3`, ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`). Mặc dù `Precision = 1.0`, judge bỏ sót tới **21/30 ca lỗi thật (FN = 21, Recall = 0.3)** — tức 70% câu trả lời vô ích/lệch trọng tâm vẫn được chấm `PASS`, khiến tỉ lệ lỗi quan sát chỉ là `0.09` (trong khi tỉ lệ thực sau hiệu chỉnh Rogan-Gladen là `0.30`). Nếu dùng `helpful` làm CI gate, hệ thống sẽ cho lọt hàng loạt bản hồi quy tệ (false pass).
- **Rủi ro còn lại:** Judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có tập held-out thật, và không dùng LLM judge để chấm tiền/approval (luôn chấm bằng code).
