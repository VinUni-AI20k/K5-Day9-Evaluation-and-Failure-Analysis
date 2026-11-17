# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có | Có thể dùng cho đánh giá giọng điệu; tiếp tục theo dõi trên nhãn mới. |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không | Loại khỏi gate; 21/30 lỗi thật bị bỏ sót. |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người | Cách xưng hô “em”, “nha” quá suồng sã; thêm ví dụ giọng thân mật quá mức vào rubric tone. |
| 2 | H-017 | PASS | FAIL | Người | “Bạn ơi”, “nha” không phù hợp ngữ cảnh khách lớn tuổi; rubric cần xét đối tượng nhận. |
| 3 | H-029 | PASS | FAIL | Người | “Không cần nhắn thêm” là mệnh lệnh gạt khách đi; không chỉ nhận diện các từ lịch sự ở đầu câu. |
| 4 | H-042 | FAIL | PASS | Người | Câu ngắn nhưng rõ và lịch sự; không bắt buộc có lời xin lỗi khi thông báo hoàn tiền. |
| 5 | H-051 | FAIL | PASS | Người | “Refund” được phép trong cách nói của CS LogiX; không tự động phạt mọi từ tiếng Anh. |

## Kết luận
- `tone_ok` đạt cả ba ngưỡng. Ma trận nhầm lẫn: TP=24, FP=4, FN=6, TN=66; ước lượng tỉ lệ lỗi hiệu chỉnh Rogan–Gladen là 0.300 so với tỉ lệ judge quan sát 0.280. Năm bất đồng trên được đối chiếu với ghi chú gán nhãn trong CSV công khai; các chỉnh sửa rubric là đề xuất, chưa được đo lại trên tập mới.
- `helpful` không được dùng làm gate: TP=9, FP=0, FN=21, TN=70. Precision 1.000 không bù được recall 0.300 và κ 0.375. Các case HL-015, HL-016, HL-020, HL-028, HL-035 đều bị judge cho PASS dù câu trả lời báo số tiền khác ledger; lỗi tiền cần grader code đối chiếu ledger, không chỉ judge đọc reply.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
