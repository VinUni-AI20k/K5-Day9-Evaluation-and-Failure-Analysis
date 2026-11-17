# Judge audit

Chạy `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5` và lệnh tương ứng với `judge_helpful_public.csv`.

| Tiêu chí | n | κ | Precision | Recall | Floors κ≥0.6, P≥0.8, R≥0.7 | Quyết định |
|---|---:|---:|---:|---:|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt | Có thể dùng như metric phụ sau khi hiệu chỉnh; không thay safety/code graders. |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt κ và recall | Loại khỏi gate; judge bỏ sót 70% nhãn FAIL. |

## Audit bất đồng

Dùng `python -m lab9.judge --csv <file> --audit 5` để in năm bất đồng đầu tiên. Với từng dòng, người audit cần đối chiếu ticket, facts DB, policy và ledger; ưu tiên nguồn DB/policy cho sự kiện và số tiền. Các bất đồng tone có thể do rubric trộn văn phong với tính lịch sự; sửa rubric để chỉ chấm tiêu chí quan sát được và không cho judge suy diễn dữ kiện. Các phán quyết cụ thể được lưu trong CSV replay công khai, không tự tạo nhãn người khi chưa có bằng chứng độc lập.

## Kết luận

Judge tone đạt floors trên bộ replay nhưng chưa có held-out human labels, nên chỉ là tín hiệu phụ. Judge helpful không đạt calibration floors và có nguy cơ chấm “nghe hợp lý” thay cho đúng chính sách; không dùng làm merge gate. Rogan–Gladen chỉ hiệu chỉnh prevalence khi sensitivity/specificity phù hợp với quần thể triển khai.

| Case | Judge / người | Ai đúng và ghi chú |
|---|---|---|
| H-008 | PASS / FAIL | Người đúng: câu quá suồng sã (“em”, “nha”); rubric cần đánh giá mức lịch sự theo ngữ cảnh, không đồng nhất thân mật với phù hợp. |
| H-017 | PASS / FAIL | Người đúng: “bạn ơi” không phù hợp ngữ cảnh khách lớn tuổi; rubric phải xét xưng hô. |
| H-029 | PASS / FAIL | Người đúng: “không cần nhắn thêm” mang giọng ra lệnh; từ mở đầu “Dạ” không cứu được phần còn lại. |
| H-042 | FAIL / PASS | Người đúng: trả lời ngắn nhưng đủ thông tin; không bắt buộc phải xin lỗi trong mọi ca. |
| H-051 | FAIL / PASS | Người đúng: “refund” được CS LogiX cho phép; không phạt từ tiếng Anh nếu rubric không cấm. |

Kết luận trên đối chiếu cột `note` trong CSV replay và nhãn human đã cung cấp. Các ví dụ cho thấy judge có cả false negative lẫn false positive do áp dụng rubric thiếu ngữ cảnh.
