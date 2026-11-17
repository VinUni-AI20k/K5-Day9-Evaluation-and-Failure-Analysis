# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.8 | Có | Dùng: đạt cả ba ngưỡng trên tập replay |
| helpful | 100 | 0.375 | 1.0 | 0.3 | Không | Loại khỏi gate: kappa và recall dưới ngưỡng |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người | Xưng “em”, dùng “nha” quá suồng sã; rubric cần phân biệt thân thiện với thiếu trang trọng. |
| 2 | H-017 | PASS | FAIL | Người, theo ngữ cảnh ghi trong CSV | Xưng “bạn” với khách lớn tuổi; rubric cần yêu cầu xét ngữ cảnh xưng hô, không chỉ nhìn lời chào. |
| 3 | H-029 | PASS | FAIL | Người | Câu “không cần nhắn thêm” mang giọng ra lệnh; rubric cần xét cả câu, không chỉ “Dạ, vui lòng”. |
| 4 | H-042 | FAIL | PASS | Người | Câu ngắn nhưng lịch sự và đủ ý; rubric không nên bắt buộc xin lỗi trong mọi trường hợp. |
| 5 | H-051 | FAIL | PASS | Người, theo quy định ghi trong CSV | LogiX cho phép dùng “refund”; rubric cần liệt kê thuật ngữ tiếng Anh được chấp nhận. |

## Kết luận
- Loại helpful khỏi gate: TP=9, FP=0, FN=21, TN=70; recall 0.3 và kappa 0.375 dưới ngưỡng.
- tone_ok đạt ngưỡng trên tập replay công khai, nhưng cần kiểm tra lại sau khi sửa rubric và dùng nhãn người trên tập held-out mới.