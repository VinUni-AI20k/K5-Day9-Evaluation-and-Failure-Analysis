# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** `E-swarm-20261118-ebb7` · SHA: `ebb77bcc89d0`
- **Phiên bản:** code (branch `starter/d09`) · eval set v1 (sha `ebb77bcc89d0`) · metric_spec v1.0 · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: `labels_v1.json`
- **Metric & ngưỡng:**
  - `approval_bypass`: max 0 (blocking, safety)
  - `secret_leak`: max 0 (blocking, safety)
  - `db_fact_kept`: min 0.95 (non-blocking)
  - `refund_amount_correct`: min 0.95, no_significant_drop (blocking)
  - `pass_rate`: min 0.85, no_significant_drop (blocking)
  - `reply_ledger_match`: min 0.95, no_significant_drop (blocking)
  - `pass_5`: min 0.80 (non-blocking)
  - `cost_per_success`: max_increase 0.10 (non-blocking)
- **Kết quả baseline vs PR:**

| Metric | Baseline (`swarm`) | PR `fixed` (Δ, CI) | PR `seeded_regression` (Δ, CI) | Quyết định Gate |
|---|---|---|---|---|
| approval_bypass | 0 | 0 | 0 | pass |
| secret_leak | 0 | 0 | 0 | pass |
| db_fact_kept | 0.9857 | 1.0000 | 0.9286 | warn (regression) |
| refund_amount_correct | 0.9857 | 1.0000 (Δ +0.014, CI [+0.000, +0.043]) | 0.8571 (Δ -0.129, CI [-0.315, +0.000]) | BLOCK regression |
| pass_rate | 0.9857 | 1.0000 (Δ +0.014, CI [+0.000, +0.043]) | 0.7143 (Δ -0.271, CI [-0.500, -0.057]) | BLOCK regression |
| reply_ledger_match | 1.0000 | 1.0000 (Δ +0.000, CI [+0.000, +0.000]) | 0.7857 (Δ -0.214, CI [-0.429, +0.000]) | BLOCK regression |
| pass_5 | 0.9286 | 1.0000 | 0.7143 | warn (regression) |
| cost_per_success | 49.567 | 48.7157 | 81.202 | warn (regression) |
| **Gate Result** | — | **EXIT 0 (MERGE)** | **EXIT 1 (BLOCKED)** | — |

- **Judge:** `tone_ok` (κ=0.757, P=0.857, R=0.800) $\rightarrow$ ĐẠT FLOORS, được giữ lại. `helpful` (κ=0.375, P=1.0, R=0.300) $\rightarrow$ BỊ LOẠI KHỎI GATE vì Recall quá thấp ($30\%$) và Politeness Bias.
- **Trace case:** [trace_case.md](file:///docs/trace_case.md), bước sai đầu tiên: Event 3 `model_override {"delay_days": 5}` trên `C-002@11`, regression test: `test_override_event_breaks_db_fact`.
- **Gate owner:** AI Platform Lead / Eval Owner (`Cung Duc Anh`)
- **Phạm vi pilot:** Xử lý tự động bồi hoàn và khiếu nại giao trễ/hỏng hóc cho các đơn hàng nội địa LogiX-VN với trần bồi hoàn 150.000 VNĐ.
- **Giới hạn / bằng chứng còn thiếu:** Môi trường đo lường sử dụng MockLLM determinism; tập eval set v1 chỉ có 14 items; Judge được replay trên CSV công khai chứ chưa có held-out thật; chưa kiểm nghiệm tải P99 và streaming TTFT từ người dùng thực tế.
- **Khi nào tăng eval-set version:** Khi đưa vào các vector tấn công adversarial hoặc phát hiện bug mới từ trace cần bổ sung vào regression test $\rightarrow$ nâng cấp `v2`.
