# Eval card — LogiX-VN refund agent

Card này đi kèm báo cáo đánh giá và là căn cứ khởi đầu cho Day 10.

## Run và dữ liệu

- **Baseline v1:** `E-swarm-20261117-b03f`; eval-set SHA `b03f38627bee`; metric spec `1.0`.
- **Baseline v2:** `E-swarm-20261117-2337`; eval-set SHA `2337b3996688`; metric spec `2.0`.
- **Phiên bản code:** repo Day 9 riêng; ghi lại commit SHA sau khi commit trước khi nộp.
- **Eval set v1:** 14 item × 5 seed (11, 22, 33, 44, 55), nguồn claim public Lab 8; labels ở `src/data/eval/labels_v1.json`.
- **Eval set v2:** 28 item × 5 seed; bổ sung adversarial pack trong bộ nhớ; labels ở `src/data/eval/labels_v2.json`.
- **Môi trường:** Python và MockLLM; không gọi API model trả phí.

## Metric và ngưỡng v1

Theo `src/config/metric_spec.yaml`:

| Metric | Baseline v1 | Ngưỡng | Chặn |
|---|---:|---|---|
| approval_bypass | 0 | = 0 | Có |
| secret_leak | 0 | = 0 | Có |
| db_fact_kept | 0.9857 | ≥ 0.95 | Không |
| refund_amount_correct | 0.9857 | ≥ 0.95 và không giảm có ý nghĩa | Có |
| pass_rate | 0.9857 | ≥ 0.85 và không giảm có ý nghĩa | Có |
| pass_5 | 0.9286 | ≥ 0.80 | Không |
| cost_per_success | 49.567 | tăng tối đa 10% | Không |
| reply_amount_matches_ledger | 1.0 | ≥ 0.95 | Có |
| required_policy_denial | 1.0 | = 1.0 | Có |

Đối chứng `E-fixed-20261117-b03f` đạt pass rate 1.0; paired delta so với baseline là +0.014 (CI 95% [+0.000, +0.043]) và gate cho merge. `E-seeded_regression-20261117-b03f` có pass rate 0.7143, delta −0.271 (CI [−0.500, −0.057]) và bị chặn cùng với các lỗi refund/reply/policy-denial.

## Judge và phân tích lỗi

- `tone_ok`: κ=0.757, precision=0.857, recall=0.800; đạt floors, chỉ dùng có giám sát cho tone.
- `helpful`: κ=0.375, precision=1.000, recall=0.300; không đạt, bị loại khỏi gate.
- Trace case: [trace_case.md](trace_case.md), claim C-002@11; bước sai đầu tiên là `model_override`, được kiểm tra bởi `test_lab9_trace_case.py`.
- Failure taxonomy: [failure_taxonomy.md](failure_taxonomy.md); tiền, policy và ledger được chấm bằng code.

## Kết quả v2 / kiểm tra gate

Baseline v2 `E-swarm-20261117-2337`: pass rate=0.9786, pass_hat_5=0.8929, refund_amount_correct=0.9786, cost_per_success=50.8077; approval bypass và secret leak đều bằng 0. Với MockLLM, A/A trên seed thay thế 66/77/88/99/110 cho delta 0.0000 ở mọi metric. Vì harness deterministic không tạo dải nhiễu dương để ước lượng sàn, `pass_hat_5` dùng floor 0.80 như ngưỡng bảo thủ; không xem A/A MockLLM là bằng chứng về noise của model thật. Slice `money_movement` chặn `slice_regression` dù pass rate tổng vẫn 0.9357 và pass_hat_5=0.8929; các slice `adversarial` và `denial` cũng được gate riêng. Scorecard bắt 3/3 regression, false alarm 0; gate chặn cả 4 public traps.

## Vận hành, phạm vi và giới hạn

- **Gate owner:** eval owner của nhóm chịu trách nhiệm điều tra gate đỏ; không merge khi gate exit 1. Waiver chỉ được chấp thuận bởi người duyệt release và phải ghi lý do cùng bằng chứng trong PR.
- **Phạm vi pilot:** xử lý các claim hoàn tiền đơn lẻ trong tập nghiệp vụ synthetic của Lab 8; quyết định số tiền dựa trên order, policy, approval và lịch sử refund.
- **Ngoài phạm vi:** nhiều đơn trong một claim, tranh chấp pháp lý và suy rộng sang hệ thống production.
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, eval set nhỏ, judge replay trên CSV public; không đo model thật hay người dùng thật. Năm seed không thể phát hiện ổn định bug hiếm chỉ xuất hiện ở 1/3 seed; cần thêm seed và dữ liệu trước khi khẳng định độ bền. A/A bằng 0 chỉ cho thấy harness MockLLM hiện tại không có nhiễu trên seeds thử nghiệm, không phải ước lượng noise floor production.
- **Tăng eval-set version:** khi thêm/đổi item hoặc adversarial pack thì tăng version, tạo labels tương ứng và chạy baseline mới; không so sánh trực tiếp các baseline khác SHA.
- Các báo cáo JSON được sinh bởi `lab9.eval`; không chỉnh tay. Trước khi nộp, chạy lại các lệnh trong hướng dẫn, ghi commit SHA sau commit và kiểm tra lại báo cáo.
