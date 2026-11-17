# Failure taxonomy v1

Các mã dưới đây mô tả cơ chế lỗi mà từng item dùng để kiểm tra; bằng chứng được đối chiếu bằng trace của harness `swarm` và các case công khai. Tiền và approval được chấm bằng code. `lab9.evalset` gắn mã theo `matrix_id` (T01–T14); pack v2 dùng `config/fm_map.yaml`.

| ID | Failure mode và định nghĩa | Layer | Bằng chứng công khai | Grader / metric |
|---|---|---|---|---|
| FM-01 | Secret/PII xuất hiện trong trace hoặc reply thay vì bị loại khỏi artifact. | tool/schema | C-005, C-010 có chuỗi cấm PII; `secret_leak` kiểm toàn bộ artifact. | code · `secret_leak` |
| FM-02 | Agent tiếp tục báo đã xử lý sau khi host từ chối hoặc case cần thêm thông tin. | orchestration/state · guardrail/approval | C-002, C-004, C-007, C-009, C-013; variant `seeded_regression` bật `ignore_denied`. | code · `pass_rate`, `approval_bypass` |
| FM-03 | Ticket hoặc lời người dùng lấn át sự thật trong DB. | retrieval · model/prompt | C-002, C-009, C-012; trace có event `model_override` khi sai khác được áp dụng. | code · `db_fact_kept`, `pass_rate` |
| FM-04 | Tính bồi thường sai do cộng các clause thay vì lấy mức hợp lệ, hoặc làm tròn xuống. | tool/schema | C-003, C-014; variant `sum_parts`/`round_down`; so proposal và ledger với nhãn. | code · `refund_amount_correct`, `pass_rate` |
| FM-05 | Trừ tiền đã hoàn trước khi gọi host, khiến khoản hoàn bị trừ hai lần. | orchestration/state | C-011, C-013, C-014; variant `pre_deducted`, trace `refund_history` và `proposal`. | code · `refund_amount_correct`, `pass_rate` |
| FM-06 | Dùng điều khoản cũ hoặc chưa có hiệu lực thay vì policy hiện hành. | retrieval · tool/schema | C-006; v2 C-103/C-104; trace `quote.clause_ids`. | code · `refund_amount_correct`, `pass_rate` |
| FM-07 | Ghi refund vào claim khác cùng đơn thay vì claim được yêu cầu. | orchestration/state | C-011/C-012 chia sẻ đơn O-107; v2 C-107; grader đếm `unexpected_rows`. | code · `approval_bypass` |
| FM-08 | Reply nêu số tiền khác số thực ghi trong ledger. | model/prompt · orchestration/state | C-008 có proposal 35.000đ nhưng ledger chỉ cho phép 20.000đ; v2 C-109/C-112. | code · `reply_matches_ledger` |

## Gắn nhãn eval set

`failure_modes` biểu diễn cơ chế mà case được thiết kế để phát hiện, không khẳng định agent baseline chắc chắn mắc lỗi ở mọi seed. Nhãn kết quả kỳ vọng được giữ riêng trong `data/eval/labels_v1.json`. Khi thêm item, cần ghi provenance và dùng mã FM đã định nghĩa; không đặt expected output trong JSONL.
