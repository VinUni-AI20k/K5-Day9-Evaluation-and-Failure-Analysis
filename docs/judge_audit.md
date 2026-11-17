# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (κ≥0.6, P≥0.8, R≥0.7) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (κ < 0.6, R < 0.7) | loại |

## ≥5 case audit thủ công (trích xuất từ judge_helpful)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | HL-015 | PASS | FAIL | Người đúng | Agent báo hoàn 55.000đ nhưng ledger chỉ ghi 40.000đ. Judge bị đánh lừa bởi văn phong lịch sự và không kiểm tra dữ liệu thật. |
| 2 | HL-016 | PASS | FAIL | Người đúng | Agent báo hoàn 55.000đ trong khi ledger ghi 35.000đ. Câu trả lời chứa lời xin lỗi dài dòng làm judge chấm PASS. |
| 3 | HL-020 | PASS | FAIL | Người đúng | Agent báo hoàn 90.000đ nhưng thực tế đơn hàng bị từ chối hoàn tiền (0đ). Judge không phát hiện sự sai lệch logic. |
| 4 | HL-028 | PASS | FAIL | Người đúng | Câu trả lời xin lỗi lịch sự nhưng không cung cấp thông tin xử lý đơn hàng hay hướng dẫn tiếp theo. |
| 5 | HL-035 | PASS | FAIL | Người đúng | Văn bản trôi chảy nhưng thiếu hành động cụ thể, judge nhầm lẫn giữa tính lịch sự và tính đúng đắn hữu ích. |

## Kết luận
- **Tiêu chí bị loại**: `helpful` bị loại hoàn toàn khỏi các release gate.
  - *Lý do*: Ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` cho thấy Judge bỏ sót đến 21 trên tổng số 30 trường hợp lỗi nghiêm trọng (Recall chỉ đạt 0.300 và Cohen's Kappa chỉ đạt 0.375, thấp hơn nhiều so với ngưỡng sàn 0.6). Judge bị thiên kiến bởi văn phong trôi chảy, lịch sự và không phát hiện được sự thật sai lệch.
- **Rủi ro còn lại**: Judge `tone_ok` chỉ mới được kiểm tra trên dữ liệu replay đã công khai (100 dòng); trong môi trường production cần thu thập thêm tập held-out mới từ người dùng thật để tránh overfitting rubric.
