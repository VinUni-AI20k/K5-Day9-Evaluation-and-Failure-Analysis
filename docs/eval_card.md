# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261117-eb7e`; eval set SHA `eb7e3773c201`.
- **Phiên bản:** code và grader dựa trên checkpoint `4bf6056`; mapping C-001 được cập nhật sau checkpoint; eval set v1; metric spec `1.0`; seeds 11/22/33/44/55.
- **Eval set:** v1, 14 item × 5 seed, nguồn `lab8_public`; nhãn tách riêng trong `labels_v1.json`.
- **Metric & ngưỡng:** `approval_bypass` và `secret_leak` tối đa 0; `refund_amount_correct` và `reply_matches_ledger` tối thiểu 0.95; `pass_rate` tối thiểu 0.85. Ba metric năng lực này còn yêu cầu không giảm có ý nghĩa so với baseline và đều chặn gate. `db_fact_kept` và `proposal_amount_correct` có ngưỡng theo dõi tối thiểu 0.95, không chặn gate. Nguồn: `src/config/metric_spec.yaml`.
- **Kết quả baseline vs PR:** bảng + paired CI

| Phiên bản | Run ID | pass_rate | Δ so với baseline | CI 95% | Gate |
|---|---|---:|---:|---|---|
| swarm (baseline) | E-swarm-20261117-eb7e | 0.9857 | — | — | Mốc so sánh |
| fixed | E-fixed-20261117-eb7e | 1.0000 | +0.014 | [0.000, 0.043] | exit 0 — merge |
| seeded_regression | E-seeded_regression-20261117-eb7e | 0.7143 | −0.271 | [−0.500, −0.057] | exit 1 — blocked |

- **Judge:** `tone_ok` đạt ngưỡng trên tập replay: κ=0.757, precision=0.857, recall=0.800. `helpful` bị loại khỏi gate vì κ=0.375 và recall=0.300 dưới ngưỡng; xem `docs/judge_audit.md`.
- **Trace case:** `docs/trace_case.md` — C-002@11, bước sai đầu tiên là event 3 `model_override`; regression test `tests/test_lab9_trace_case.py` đã đạt.
- **Gate owner:** Người thực hiện PR kiểm tra report và xử lý nguyên nhân khi gate exit 1.
- **Phạm vi pilot:** Đánh giá offline agent xử lý claim hoàn tiền LogiX-VN trên dữ liệu công khai; chưa triển khai cho người dùng thật.
- **Giới hạn / bằng chứng còn thiếu:** MockLLM không đại diện đầy đủ cho model thật; eval set chỉ có 14 item; judge dùng nhãn replay công khai, chưa có tập held-out mới; chưa đo trên người dùng thật. Với 5 seed, lỗi hiếm xuất hiện ở 1/3 seed không được phát hiện ổn định.
- **Khi nào tăng eval-set version:** Khi thêm, bớt hoặc thay đổi item hay nhãn; sinh baseline mới và ghi rõ phiên bản để tránh so sánh các tập khác nhau.

## Eval set v2 — Advanced / Expert

- Baseline: `E-swarm-20261117-ab26`, SHA `ab26394698e2`, 28 item × 5 seed.
- A/A: hai bộ seed 11/22/33/44/55 và 66/77/88/99/110 cho Δ = 0 trên MockLLM. Baseline `pass_hat_5 = 0.8929`; chọn ngưỡng blocking 0.80 theo rubric.
- Slice `money_movement`: baseline pass_rate 1.0; slice_regression đạt 0.85 và bị chặn dưới ngưỡng 0.90. Slice `adversarial` có ngưỡng 0.90.
- `flaky_regression`: pass_hat_5 = 0.5714, bị chặn dưới ngưỡng 0.80; trong lần chạy này pass_rate và slice money_movement cũng chặn.
- Mutation công khai: 3/3 regression bị chặn, 0 báo nhầm trên fixed và honest_refactor.
- Integrity: bốn trap công khai bị chặn; baseline so với chính nó được cho qua.
- Giới hạn: A/A trên MockLLM có thể cho Δ = 0; model thật có thể có nhiễu, cần đo lại trước khi chọn ngưỡng. Lỗi hiếm xuất hiện ở 1/3 seed không được phát hiện ổn định chỉ với 5 seed.
