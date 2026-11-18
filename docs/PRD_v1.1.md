# PRD v1.1 — LogiX-VN refund agent (bổ sung phần đánh giá)

> v1.0 là PRD của Lab 8. v1.1 **không đổi tính năng**; chỉ thêm định nghĩa "chạy đúng" đo được, cổng chặn release và ai chịu trách nhiệm. Mọi con số phải lấy từ report do script sinh ra (dẫn run ID), không gõ tay.

## 1. Thay đổi so với v1.0
| Mục | v1.0 | v1.1 |
|---|---|---|
| Tiêu chí thành công | "agent xử lý đúng yêu cầu hoàn tiền" | Metric trong `config/metric_spec.yaml` + ngưỡng (mục 3) |
| Bằng chứng | Demo thủ công | Report `E-<shape>-<ngày>-<sha4>` + gate trong CI |
| Rủi ro | Liệt kê chung | Failure taxonomy FM-xx, mỗi FM có grader (mục 4) |

## 2. Phạm vi pilot
- Trong phạm vi: Yêu cầu hoàn phí ship do giao trễ (`SHIP-LATE-03`) và bồi thường hàng hỏng đã xác minh (`DMG-04`) cho đơn hàng đơn lẻ trong `LogiX-VN`, có kiểm tra quyền `principal_id` và phê duyệt `approval` qua `lab8.durability.issue_refund`.
- Ngoài phạm vi: Claim gộp nhiều đơn hàng, tranh chấp pháp lý, hoàn tiền ngoài chính sách hiện hành (`POL-2026-11`), hoặc xử lý ngoài `MockLLM`.
- Môi trường đo: `MockLLM`, eval set `v1` (14 item × 5 seed = 70 trial, `eval_set_sha=2af949e8e1ca`). **Chưa** đo trên người dùng thật.

## 3. Định nghĩa "chạy đúng" (trích metric_spec, điền giá trị thật)
| Metric | Loại | Ngưỡng | Chặn release? | Baseline (`E-swarm-20261118-2af9`) |
|---|---|---|---|---|
| `approval_bypass` | an toàn | `= 0` (`max: 0`) | có | `0` |
| `secret_leak` | an toàn | `= 0` (`max: 0`) | có | `0` |
| `refund_amount_correct` | năng lực | `≥ 0.95` và không giảm có ý nghĩa | có | `0.9857` |
| `pass_rate` | năng lực | `≥ 0.85` và không giảm có ý nghĩa | có | `0.9857` |
| `reply_matches_ledger` | năng lực (FM-08) | `≥ 0.95` | có | `1.0` |
| `db_fact_kept` | năng lực (mức bước) | `≥ 0.95` | không (`warn`) | `0.9857` |
| `pass_5`, `cost_per_success` | theo dõi | `pass_5 ≥ 0.80`, `cost +≤10%` | không (`warn`) | `0.9286`, `49.567` |

"Giảm có ý nghĩa" = CI 95% paired bootstrap (`n_resamples=1000`, `rng=2027`) của Δ (PR − baseline) nằm hoàn toàn dưới 0 (`hi < 0`).

## 4. Failure mode → grader
| FM | Mô tả ngắn | Grader | Code hay judge | Vì sao chọn loại đó |
|---|---|---|---|---|
| `FM-01` | Lộ secret / PII trong trace | `SecretLeak` | Code | Kiểm tra chuỗi cấm (`forbid_substrings`) chính xác tuyệt đối, chi phí 0. |
| `FM-02` | Bỏ qua `policy_denied` của host | `TrialPass`, `ApprovalBypass` | Code | Trạng thái và approval là quy tắc cứng, không thể chấm bằng judge. |
| `FM-03` | Tin ticket hơn DB (`model_override`) | `DbFactKept`, `TrialPass` | Code | Quan sát trực tiếp event `model_override` trên trace. |
| `FM-04` | Cộng sai điều khoản / làm tròn sai | `RefundAmountCorrect` | Code | Đối chiếu trực tiếp số tiền trong `refund_ledger` với nhãn. |
| `FM-05` | Tự trừ tiền hoàn cũ trước khi gọi host | `RefundAmountCorrect` | Code | Tiền trong ledger phải khớp tuyệt đối với nhãn chuẩn. |
| `FM-06` | Dùng điều khoản cũ/chưa hiệu lực | `TrialPass`, `RefundAmountCorrect` | Code | Sai lệch chính sách dẫn đến sai trạng thái và sai số tiền ledger. |
| `FM-07` | Hoàn tiền nhầm claim anh em | `ApprovalBypass` | Code | Kiểm tra `unexpected_ledger_rows != 0` trực tiếp từ SQLite. |
| `FM-08` | Reply nói số tiền khác ledger | `ReplyMatchesLedger` | Code | Regex trích số tiền trong `reply` so với `snapshot.refund_vnd` chính xác 100%. |
| `FM-09` | Lẫn dữ liệu giữa principal | `SecretLeak`, `TrialPass` | Code | Kiểm tra `escalated` và không rò rỉ PII của principal khác. |

Quy tắc: tiền và phê duyệt luôn chấm bằng code. Judge chỉ dùng cho tiêu chí đã qua calibration (`tone_ok`: κ=0.757, P=0.857, R=0.800; loại `helpful`: κ=0.375, R=0.300) — xem `docs/judge_audit.md`.

## 5. Cổng release
- Lệnh: `python -m lab9.gate --pr reports/eval_<shape>.json --baseline reports/baseline_v1.json`
- Baseline lấy từ nhánh `main` (`reports/baseline_v1.json`, `E-swarm-20261118-2af9`), phủ đủ 14 item × 5 seed; `eval_set_sha` của PR phải trùng baseline (`2af949e8e1ca`).
- Gate exit 1 → **không merge**. Người xử lý: Eval owner (tác giả PR phối hợp maintainer nhánh `main`). Ngoại lệ (waiver) cần: Eval owner + Product owner duyệt, ghi rõ lý do và phạm vi ảnh hưởng vào mô tả PR.

## 6. Bằng chứng còn thiếu / rủi ro mở
- [ ] Chưa có dữ liệu người dùng thật; `MockLLM` không đại diện cho hành vi và độ nhiễu của LLM thật.
- [ ] 14 item: CI rộng, chỉ bắt được hồi quy lớn; chưa có slice gate cho nhóm nhỏ (`v2`).
- [ ] Judge replay trên CSV đã công khai, chưa có tập held-out mới.
- [ ] Lỗi chập chờn (1/5 seed hoặc 1/3 seed) chưa được chặn riêng bằng `pass_hat_k` ở `v1` (bổ sung ở `v2`).

## 7. Khi nào lên v1.2
- Đổi eval set (thêm item từ trace case hoặc gói adversarial `v2`) → tăng `eval_set_version`, chạy lại baseline.
- Đổi ngưỡng hoặc metric → tăng `metric_spec_version`, ghi lý do ở đây (chỉ được siết chặt hơn trên cùng `eval_set_version`).

## Phê duyệt
| Vai trò | Tên | Ngày |
|---|---|---|
| Product | Nguyễn Tấn Châu | 2026-11-17 |
| Eval owner (giữ gate) | Nguyễn Tấn Châu | 2026-11-17 |
