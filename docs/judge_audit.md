# Judge audit M2

Chạy từ `src/`:

```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 21
```

Trong hai phép tính, `FAIL` là lớp dương vì mục tiêu của judge là tìm câu lỗi. Sàn calibration: κ ≥ 0,6; precision ≥ 0,8; recall ≥ 0,7.

| Tiêu chí | n | TP / FP / FN / TN | κ | Precision | Recall | Tỉ lệ FAIL judge / đã hiệu chỉnh | Quyết định |
|---|---:|---|---:|---:|---:|---|---|
| tone_ok | 100 | 24 / 4 / 6 / 66 | 0,757 | 0,857 | 0,800 | 0,28 / 0,30 | Qua sàn; dùng cho đánh giá giọng điệu sau khi sửa rubric và nhãn sai |
| helpful | 100 | 9 / 0 / 21 / 70 | 0,375 | 1,000 | 0,300 | 0,09 / 0,30 | Loại khỏi gate |

## Audit bất đồng

| Case | Judge / người | Ai đúng? | Lý do và chỗ cần sửa |
|---|---|---|---|
| H-008 | PASS / FAIL | Người | "Em ... nha" quá suồng sã trong trả lời khách. Rubric cần nêu rõ cách xưng hô và mức thân mật. |
| H-029 | PASS / FAIL | Người | "Không cần nhắn thêm" là câu ra lệnh. Judge đang bị các từ mở đầu lịch sự che phần còn lại; rubric phải xét cả câu. |
| H-042 | FAIL / PASS | Người | Câu ngắn nhưng đã có đơn, tiền và thời gian tiền về. Bỏ yêu cầu ngầm rằng mọi câu phải có lời xin lỗi. |
| H-051 | FAIL / PASS | Người | CS LogiX cho phép dùng từ "refund". Thêm từ này vào danh sách thuật ngữ được chấp nhận. |
| H-063 | PASS / FAIL | Người | "Sẽ hoàn thêm" hứa một giao dịch chưa có trong kết quả. Rubric phải phạt lời hứa hoàn tiền không có căn cứ; đối chiếu ledger bằng code. |

## Quyết định

`helpful` bỏ sót 21/30 ca FAIL, nhiều ca là tiền trong reply khác ledger. Precision 1,0 chỉ cho biết 9 ca bị judge bắt đều đúng; recall 0,3 và κ 0,375 dưới sàn. Không dùng judge này làm metric blocking. Số tiền và approval phải chấm bằng code; sau khi sửa rubric mới hiệu chuẩn lại judge trên tập có nhãn người.

Với `tone_ok`, H-081 cho thấy nhãn người cũng có thể sai. Kết quả hiện tại là replay trên CSV công khai, nên chưa chứng minh judge giữ được chất lượng trên câu trả lời mới. Cần một tập held-out có người gán nhãn trước khi đưa judge vào gate thật.
