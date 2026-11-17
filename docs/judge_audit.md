# Judge audit

Chạy replay offline:

```powershell
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

PASS/FAIL được xem như classifier, trong đó FAIL là positive. Hiệu chỉnh fail-rate dùng Rogan–Gladen với sensitivity=recall và specificity từ confusion matrix.

| Tiêu chí | n | κ | Precision | Recall | Đạt κ≥0.6, P≥0.8, R≥0.7? | Quyết định |
|---|---:|---:|---:|---:|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có | Dùng có giám sát; chỉ là tín hiệu ngôn ngữ, không quyết định tiền/quyền |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không | Loại; bỏ sót 70% trường hợp human gắn FAIL |

Tỉ lệ FAIL quan sát của `tone_ok` là 0.28; sau hiệu chỉnh theo sensitivity 0.80 và specificity 66/70, ước lượng là 0.30. Với `helpful`, tỉ lệ quan sát là 0.09 nhưng độ nhạy chỉ 0.30; hiệu chỉnh cho ước lượng 0.30, kém ổn định và không đủ điều kiện sử dụng.

## Năm bất đồng cần audit

| # | Case | Judge | Human | Ai đúng? / hành động |
|---:|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Human: lời xác nhận hoàn tiền không có bằng chứng trạng thái hoặc thời gian; thêm quy tắc không suy diễn hoàn tất từ lời hứa. |
| 2 | H-017 | PASS | FAIL | Human: câu thân mật nhưng không nêu điều kiện cap/tiền thực ghi; tách tone khỏi đúng nghiệp vụ. |
| 3 | H-029 | PASS | FAIL | Human: yêu cầu chờ chung chung không đưa bước tiếp theo/thời hạn; rubric helpful cần bước hành động cụ thể. |
| 4 | H-042 | FAIL | PASS | Judge quá nghiêm: câu ngắn vẫn nêu số tiền và thời gian nhận rõ; thêm ví dụ PASS ngắn gọn vào rubric tone. |
| 5 | H-051 | FAIL | PASS | Judge phạt từ “refund” tiếng Anh dù nội dung lịch sự; rubric chấp nhận thuật ngữ song ngữ thường dùng. |

Các bất đồng `helpful` đầu tiên gồm HL-015/016/020/028/035: judge bỏ qua câu xin lỗi ngắn hoặc nội dung refund vì suy luận ngoài tiêu chí; vẫn loại tiêu chí này vì recall 0.30. Audit dùng nhãn replay công khai nên chưa thay thế kiểm định trên tập held-out mới.
