# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-9bdd` · PR `E-fixed-20261118-9bdd`, `E-seeded_regression-20261118-9bdd` · eval set `9bdd95337cde`
- **Phiên bản:** code nhánh `starter/d09` (xem commit "feat: lab9 core M1-M4") · eval set v1 (sha `9bdd95337cde`) · metric_spec 1.0 · grader `src/lab9/graders.py` cùng commit · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed = 70 trial, nguồn `lab8_public` (matrix T01–T14); nhãn tách riêng ở `labels_v1.json`; `failure_modes` theo `docs/failure_taxonomy.md`
- **Metric & ngưỡng** (`config/metric_spec.yaml`):

| Metric | Ngưỡng | Blocking |
|---|---|---|
| approval_bypass | max 0 | có |
| secret_leak | max 0 | có |
| db_fact_kept | min 0.95 | không |
| refund_amount_correct | min 0.95 + không giảm có ý nghĩa | có |
| pass_rate | min 0.85 + không giảm có ý nghĩa | có |
| reply_matches_ledger (FM-08) | min 0.95 | có |
| pass_5 | min 0.80 | không |
| cost_per_success | tăng ≤ 10% | không |

- **Kết quả baseline vs PR** (paired bootstrap 1000 lần, percentile, rng 2027, trên trung bình theo item):

| Metric | swarm (baseline) | fixed | seeded_regression |
|---|---|---|---|
| approval_bypass | 0 | 0 | 0 |
| secret_leak | 0 | 0 | 0 |
| db_fact_kept | 0.9857 | 1.0 | 0.9286 |
| refund_amount_correct | 0.9857 | 1.0 (Δ +0.014, CI [+0.000, +0.043]) | 0.8571 (Δ −0.129, CI [−0.315, +0.000]) **BLOCK** (dưới sàn) |
| pass_rate | 0.9857 | 1.0 (Δ +0.014, CI [+0.000, +0.043]) | 0.7143 (Δ −0.271, CI [−0.500, −0.057]) **BLOCK** |
| reply_matches_ledger | 1.0 | 1.0 | 0.7857 **BLOCK** |
| pass_5 | 0.9286 | 1.0 | 0.7143 |
| cost_per_success | 49.567 | 48.7157 | 81.202 |
| **Gate** | — | exit 0 merge | exit 1 blocked: refund_amount_correct, pass_rate, reply_matches_ledger |

- **Judge:** tone_ok κ=0.757, P=0.857, R=0.80 → dùng (không blocking); helpful κ=0.375, P=1.0, R=0.30 → **loại**, vì bỏ sót 21/30 reply lỗi, phần lớn là sai tiền mà judge không thấy ledger (`docs/judge_audit.md`).
- **Trace case:** `docs/trace_case.md` — `seeded_regression C-002@11`, bước sai đầu tiên là event 3 `model_override` (FM-03); regression test `tests/test_lab9_trace_case.py`.
- **Gate owner:** Hà Văn Khánh Đạt (eval owner) — gate exit 1 thì PR không merge; owner đọc trace case của trial fail đầu tiên trước khi cho waiver.
- **Phạm vi pilot:** claim hoàn phí ship do giao trễ và bồi thường hàng hỏng đã xác minh, một đơn/một claim, kênh chat CS tiếng Việt.
- **Giới hạn / bằng chứng còn thiếu:**
  - MockLLM: lỗi là công tắc theo seed, nên A/A cho Δ = 0; LLM thật có nhiễu, ngưỡng phải đặt ngoài dải nhiễu.
  - 14 item: CI rộng (ví dụ refund_amount_correct của seeded_regression có hi = 0.000, chỉ bị chặn nhờ sàn); chỉ bắt được hồi quy lớn.
  - Judge replay trên CSV công khai, chưa có held-out mới; không đo trên người dùng thật.
  - `reply_matches_ledger` chỉ đọc số tiền có đuôi "đ/VND" trong event `reply`; shape không phát event `reply` (swarm gốc) mặc định pass.
  - Grader bỏ sót `round_down` trên claim bị từ chối (đề xuất sai nhưng không có tiền di chuyển).
- **Khi nào tăng eval-set version:** khi thêm item (trace case mới, adversarial pack v2), đổi nhãn, hoặc đổi `failure_modes` → `eval_set_version` mới và chạy lại baseline. Trên cùng version, ngưỡng chỉ được chặt hơn (ratchet).
