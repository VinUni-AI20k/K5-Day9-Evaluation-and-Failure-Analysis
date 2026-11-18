# Judge audit

Chạy: `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10` và `... judge_helpful_public.csv --audit 20`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt — confusion tp 24 / fp 4 / fn 6 / tn 66 | **dùng** (chỉ cho tone, không cho tiền) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không đạt** κ và R — tp 9 / fp 0 / fn 21 / tn 70 | **loại** |

Tỉ lệ lỗi hiệu chỉnh Rogan-Gladen: tone quan sát 0.28 → hiệu chỉnh 0.30; helpful quan sát **0.09 → 0.30**. Judge helpful báo thấp hơn thực tế hơn 3 lần.

## Case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em/anh" suồng sã, không nêu số tiền/đơn. Rubric thêm: phải dùng "LogiX" + "anh/chị", không đoán giới tính. |
| 2 | H-070 "...hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Emoji cười trong ngữ cảnh khiếu nại. Rubric thêm: cấm emoji. |
| 3 | H-094 "Da, LogiX da hoan 40.000đ..." (không dấu) | PASS | FAIL | Người | Tiếng Việt không dấu kém chuyên nghiệp. Rubric thêm: phải có dấu đầy đủ. |
| 4 | H-029 "Dạ, vui lòng chờ... không cần nhắn thêm." | PASS | FAIL | Người | Lịch sự bề mặt nhưng chặn khách. Rubric thêm: không được ra lệnh khách ngừng liên hệ. |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người (chấp nhận được) | Judge phạt vì chữ "refund" tiếng Anh. Rubric nói rõ: thuật ngữ quen thuộc không làm fail tone. |
| 6 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn..." | FAIL | PASS | **Judge** | Người gán nhãn đọc nhầm ticket → sửa nhãn người, không sửa rubric. Bất đồng không phải lúc nào cũng là lỗi của judge. |
| 7 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ..." | FAIL | PASS | Hơi mơ hồ | Lặp "dạ" là lỗi gõ nhỏ; rubric ghi: lỗi lặp từ đơn lẻ không fail tone. |
| 8 | HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." | PASS | FAIL | Người | Lỗi người ghi: **sai tiền** (ledger 40.000đ, reply 55.000đ). Helpful không đánh giá được từ câu chữ — cần đối chiếu ledger → việc của code (`reply_matches_ledger`). |
| 9 | HL-016 "...thành thật xin lỗi... đã hoàn 55.000đ cho đơn O-404..." | PASS | FAIL | Người | Sai tiền (ledger 35.000đ) bị che bởi lời xin lỗi dài, lịch sự (verbosity bias). Judge không có ledger nên không thể bắt. |
| 10 | HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | Người | Sai xưng hô và không nêu kết quả/số tiền. Rubric helpful phải bắt buộc: xưng hô đúng + kết quả + số tiền + bước tiếp theo. |

## Kết luận
- **tone_ok** đạt floors, được dùng làm metric phụ (không blocking) cho giọng điệu. Các FN (H-008, H-017, H-070, H-094, H-029) cho thấy judge dễ dãi với văn phong suồng sã → thêm các quy tắc trên vào rubric rồi calibrate lại. H-081 là lỗi nhãn người → sửa nhãn.
- **helpful bị loại khỏi gate**: recall 0.30 nghĩa là judge bỏ sót 21/30 reply vô ích; κ 0.375 < 0.6. Precision 1.0 không cứu được vì gate cần *bắt* lỗi. Phần lớn FN có `human_failure = sai tiền` (HL-015, HL-016, HL-087 …): judge chỉ thấy câu chữ, không thấy ledger, nên về nguyên tắc không thể chấm đúng. Phần "đúng số tiền" chuyển cho grader code `reply_matches_ledger`; phần còn lại cần viết lại rubric (bắt buộc nêu kết quả, số tiền, bước tiếp) và gán nhãn người mới.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
