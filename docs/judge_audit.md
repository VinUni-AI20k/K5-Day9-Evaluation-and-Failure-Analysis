# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (backend replay, verdict của judge lưu sẵn trong CSV). FAIL là lớp dương.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | **Đạt** — tp 24, fp 4, fn 6, tn 66 | **dùng** (chỉ cho giọng văn, không chặn release) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không đạt** κ và R — tp 9, fp 0, fn 21, tn 70 | **loại** |

Tỉ lệ FAIL quan sát → hiệu chỉnh Rogan-Gladen: tone 0.28 → 0.30; helpful **0.09 → 0.30**. Judge helpful báo chỉ 9% câu trả lời có vấn đề trong khi thực tế là 30%: nó đánh giá thấp lỗi đi hơn 3 lần.

## Audit thủ công các ca bất đồng
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | tone H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã với khách khiếu nại. **Rubric:** ghi rõ xưng hô chuẩn là "LogiX – anh/chị"; "em/bạn/nha/nhé" ⇒ FAIL; thêm 2 ví dụ FAIL dạng này vào prompt. |
| 2 | tone H-017 "Dạ, bạn ơi LogiX đã hoàn…" | PASS | FAIL | Người | Cùng lỗi xưng hô ("bạn"). Judge đang hiểu "thân thiện" = tốt. **Rubric:** tách "thân thiện" khỏi "đúng mực"; tiêu chí là đúng mực. |
| 3 | tone H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh; judge chỉ khớp từ lịch sự đầu câu. **Rubric:** chấm cả câu, không chỉ kính ngữ mở đầu; câu mệnh lệnh cấm khách liên hệ ⇒ FAIL. |
| 4 | tone H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Judge phạt vì "thiếu xin lỗi". **Rubric:** xin lỗi không bắt buộc khi đã giải quyết xong; ngắn gọn, đủ ý là PASS. |
| 5 | tone H-051 "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | Người | CS LogiX cho phép từ "refund". **Rubric:** thêm danh sách từ tiếng Anh được phép (refund, ship, voucher). |
| 6 | tone H-063 "…và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người | Hứa ngoài kết quả hệ thống. Không phải lỗi giọng văn mà là lỗi nội dung ⇒ **chuyển sang grader code** (reply chỉ được nêu hành động đã có trong ledger), không nhồi vào rubric tone. |
| 7 | tone H-070 "…cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | **Rubric:** emoji cười trong ngữ cảnh khiếu nại ⇒ FAIL. |
| 8 | tone H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn…" | FAIL | PASS | **Judge** | Ghi chú cho thấy nhãn người sai (đọc nhầm ticket). **Hành động:** sửa nhãn người thành FAIL; κ thật của tone còn cao hơn số ở bảng. |
| 9 | tone H-094 "Da, LogiX da hoan 40.000đ…" | PASS | FAIL | Người | Mất dấu tiếng Việt. **Rubric:** câu không dấu/dịch máy ⇒ FAIL. |
| 10 | helpful HL-015 "…đã hoàn 55.000đ cho đơn O-112" (ledger 40.000đ) | PASS | FAIL | Người | Judge không thấy ledger nên **không thể** biết số sai. 18/21 ca bỏ sót của helpful là "sai tiền". **Hành động:** bỏ "đúng số tiền" khỏi rubric judge; giao cho grader code `reply_matches_ledger` (FM-08). |
| 11 | helpful HL-016 / HL-043 (lời xin lỗi dài + số tiền sai) | PASS | FAIL | Người | Câu dài, nhiều xin lỗi khiến judge chấm "hữu ích" dù số tiền sai: thiên lệch theo độ dài và độ lịch sự. |
| 12 | helpful HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | Người | Sai xưng hô và không nói kết quả cụ thể. Phần xưng hô do tone judge chấm; "nêu kết quả cụ thể" cần ví dụ FAIL trong rubric helpful. |

## Kết luận
- **tone_ok: dùng được.** Qua cả ba sàn (κ 0.757, P 0.857, R 0.80). Chỉ dùng làm metric theo dõi, không blocking. Vẫn sửa rubric theo các ca 1–5, 7, 9 rồi calibrate lại; sửa nhãn H-081.
- **helpful: loại, không được dùng làm gate.** Precision 1.0 nhìn thì đẹp, nhưng recall chỉ 0.30 (21/30 câu trả lời tệ bị cho qua) và κ 0.375 < 0.6. Nếu đặt làm gate, một bản PR nói sai tiền với khách gần như luôn được merge: judge có tỉ lệ fn = 70%. Tỉ lệ FAIL quan sát 9% so với 30% sau hiệu chỉnh cho thấy nó che lỗi một cách có hệ thống. Nguyên nhân gốc: 18/21 ca bỏ sót là **sai tiền**, thứ mà judge không thể chấm vì nó không thấy ledger. Theo quy tắc của lab, tiền luôn chấm bằng code: phần này đã giao cho `reply_matches_ledger` (blocking, min 1.0).
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai (và chính các ca bất đồng này đã được dùng để sửa rubric). Cần một tập nhãn người mới làm held-out thật trước khi tin số κ sau khi sửa.
