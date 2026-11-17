# Judge audit

Lệnh tái lập: `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5` và `python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5`.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---:|---:|---:|---:|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có | Có thể dùng có giám sát, chỉ cho tiêu chí tone đã hiệu chỉnh |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không | Loại khỏi gate; bỏ sót 70% reply fail theo nhãn người |

Confusion (positive = FAIL): tone `TP=24, FP=4, FN=6, TN=66`; helpful `TP=9, FP=0, FN=21, TN=70`. Rogan–Gladen: tone observed fail 0.280 → corrected 0.300; helpful 0.090 → 0.300. Helpful có precision hoàn hảo nhưng recall rất thấp; không được diễn giải precision cao thành judge tốt.

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---:|---|---|---|---|---|
| 1 | H-008: “Em đã hoàn tiền cho anh rồi nha…” | PASS | FAIL | Người | Cờ xưng “em” với khách và “nha” suồng sã; rubric tone cần quy định rõ đại từ, không chấm chỉ theo lời cảm ơn. |
| 2 | H-017: “Dạ, bạn ơi… rồi nha.” | PASS | FAIL | Người | “Bạn” không phù hợp ngữ cảnh khách hàng; thêm ví dụ negative về xưng hô thân mật quá mức. |
| 3 | H-029: “…không cần nhắn thêm.” | PASS | FAIL | Người | Câu mệnh lệnh/đóng hội thoại thiếu tôn trọng; judge bị từ khóa lịch sự “Dạ, vui lòng” đánh lạc hướng. |
| 4 | H-042: thông báo refund ngắn, rõ số tiền và thời gian | FAIL | PASS | Người | Judge đòi lời xin lỗi dù không bắt buộc; bỏ “phải xin lỗi” khỏi rubric khi câu trả lời đầy đủ và lịch sự. |
| 5 | H-051: “LogiX đã refund 90.000đ…” | FAIL | PASS | Người | Từ “refund” được CS cho phép; judge không nên phạt từ vay mượn nếu ý rõ và tone phù hợp. |

## Kết luận

- `tone_ok` đạt cả ba floors (κ≥0.6, P≥0.8, R≥0.7), nhưng chỉ đủ điều kiện hỗ trợ kiểm tra tone và vẫn cần audit mẫu.
- `helpful` bị loại do κ=0.375 và recall=0.300. Trong các bất đồng như HL-015, HL-016, HL-020, HL-028 và HL-035, người gắn FAIL vì reply nói sai số tiền, còn judge nói PASS; số tiền phải chấm bằng code đối chiếu ledger, không thể giao cho judge helpful.
- Rủi ro còn lại: replay CSV đã công khai, không phải held-out mới; một số nhãn tone có thể chủ quan. Thu thập nhãn độc lập và báo adjudication trước khi đưa judge vào production gate.
