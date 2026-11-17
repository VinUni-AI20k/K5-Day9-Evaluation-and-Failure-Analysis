# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (judge replay trên CSV công khai, FAIL là lớp dương).

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | **PASS** (tp 24, fp 4, fn 6, tn 66) | **dùng**, chỉ để báo cáo, không blocking |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **FAIL** (tp 9, fp 0, fn 21, tn 70) | **loại** |

Tỉ lệ lỗi sau hiệu chỉnh Rogan-Gladen: tone 0.28 → 0.30; helpful 0.09 → 0.30. Với helpful, judge thấy 9% lỗi trong khi tỉ lệ thật khoảng 30%: nó bỏ sót 21 trên 30 reply người chấm FAIL.

## Audit thủ công (5 bất đồng tone + 3 helpful)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã. Rubric thêm: *xưng hô phải là "LogiX"/"anh/chị"; "em/bạn/nha" = FAIL* |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ…rồi nha." | PASS | FAIL | Người | Cùng lỗi xưng hô ("bạn ơi"). Rubric: câu có "Dạ" ở đầu không làm cả câu lịch sự; chấm theo từ xưng hô, không theo từ đệm |
| 3 | H-029 "Dạ, vui lòng chờ…không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh; judge chỉ thấy "Dạ, vui lòng". Rubric thêm ví dụ âm: *câu mệnh lệnh cấm khách liên hệ = FAIL dù có kính ngữ* |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Judge phạt vì thiếu xin lỗi. Rubric ghi rõ: *xin lỗi không bắt buộc khi yêu cầu đã được giải quyết; ngắn mà đủ ý = PASS* |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | "refund" nằm trong danh sách từ CS LogiX cho phép. Rubric thêm whitelist thuật ngữ tiếng Anh (refund, ship, voucher) |
| 6 | HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." (ledger 40.000đ) | PASS | FAIL | Người | Judge không thấy ledger nên không biết số sai. Không sửa được bằng rubric, chỉ sửa bằng **code**: `ReplyMatchesLedger` (FM-08) |
| 7 | HL-016 xin lỗi 3 lần + "đã hoàn 55.000đ" (ledger 35.000đ) | PASS | FAIL | Người | Văn dài, nhiều xin lỗi làm judge cho PASS. Cùng lỗi sai tiền như #6 |
| 8 | HL-020 "đã hoàn 90.000đ cho đơn O-303" (ledger 120.000đ) | PASS | FAIL | Người | Như #6 |

Cả 8 case người đều đúng. Với tone, 3 lỗi FN cùng kiểu (judge xem kính ngữ bề mặt là đủ) và 2 lỗi FP cùng kiểu (judge áp quy tắc không có trong policy CS). Cả hai sửa được bằng rubric có ví dụ âm/dương.

## Kết luận
- **helpful bị loại.** Recall 0.30 < 0.70 và κ 0.375 < 0.6: judge bỏ sót 21/30 reply người chấm FAIL. Precision 1.0 không cứu được: một gate dựa trên judge này sẽ cho qua 70% reply có lỗi. 18/21 FN là reply **nói sai số tiền** (cột `human_failure` = "sai tiền"; 3 còn lại "sai xưng hô"). Judge bắt được đúng 0/18 lỗi sai tiền: nó không thấy ledger. Đó là việc của code đọc ledger (FM-08 → `reply_matches_ledger`, blocking), không phải của judge. Quy tắc PRD: tiền và approval luôn chấm bằng code.
- **tone_ok dùng được** (κ 0.757, P 0.857, R 0.80 đều trên sàn), nhưng chỉ làm metric báo cáo, không blocking. Recall 0.80 vẫn bỏ sót 1/5 reply sai giọng. Áp dụng 5 sửa đổi rubric ở trên rồi calibration lại trước khi cân nhắc cho chặn.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai, nên rubric mới có thể overfit đúng 5 case này. Cần một tập nhãn người mới (held-out) để đo lại κ/P/R sau khi sửa rubric.
