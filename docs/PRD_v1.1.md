# PRD v1.1 — Evaluation gate cho refund agent

## Vấn đề

Một agent có thể trả lời thuyết phục nhưng vẫn dùng sai sự thật DB, vượt approval hoặc báo số tiền không khớp ledger. Tỉ lệ pass tổng hợp có thể che lỗi hiếm hoặc lỗi chỉ nằm trong nhóm money movement.

## Mục tiêu

1. Chạy eval offline, tái lập được từ cùng code, eval set và seed.
2. Dùng code grader cho tiền, approval, secret và đối chiếu reply/ledger; judge ngôn ngữ chỉ là tín hiệu phụ sau calibration.
3. Chặn regression trước merge bằng baseline có provenance, paired bootstrap, slice gate và kiểm tra integrity.
4. Giữ nhãn tách khỏi item, report sinh tự động và eval set version bất biến.

## Người dùng và luồng

Tác giả PR chạy harness với cùng spec; CI đánh giá candidate, đối chiếu baseline cùng `(item_id, seed)`, chạy integrity checks, áp safety floors và capability thresholds. Nếu gate đỏ, reviewer dùng trace để tìm bước sai đầu tiên, thêm case regression, rồi mới xem xét merge.

## Tiêu chí chấp nhận

- Không leak secret, không refund trái approval, không để reply amount sai ledger.
- `fixed` qua gate; `seeded_regression` bị chặn trên `pass_rate`.
- Một slice money movement suy giảm bị chặn dù trung bình chung còn trên sàn.
- Report thiếu/nhân đôi rows, đổi slice labels, có evaluator failure/NaN hoặc nới threshold trong cùng version bị chặn.
- Auditability: run ID, SHA dữ liệu, seeds, metric spec và labels có thể truy ngược.

## Ngoài phạm vi và rủi ro

Không triển khai observability/OTel, LLM-as-judge trực tiếp, API keys, dữ liệu người dùng thật hay cam kết phát hiện mọi bug hiếm. Mẫu nhỏ và benchmark deterministic có thể tạo cảm giác chắc chắn quá mức; mỗi release cần ghi giới hạn và bổ sung held-out human review.
