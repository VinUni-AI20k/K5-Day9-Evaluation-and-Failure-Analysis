# M6 — A/A và độ ổn định

<!-- M6_V2_BEGIN -->
## v2 — M6: nhiễu A/A và độ ổn định pass^5

Evidence **M6-20261118-2db9b0d9c4f2**, [JSON đầy đủ](../src/reports/m6_noise_validation.json), [hướng dẫn tái lập](m6_noise_and_reliability.md). Spec **2.3**, eval-set SHA **088a201ad90e**, 28 item × 5 seed mỗi bộ; MockLLM, SQLite mới mỗi trial.

`pass@k = 1 − C(n−c,k)/C(n,k)` đo ít nhất một lần thành công; `pass^k = C(c,k)/C(n,k)` đo tất cả k lần thành công, lấy mẫu không hoàn lại. Lấy trung bình ước lượng theo item. Từ chối n<1, c ngoài [0,n], k ngoài [1,n] và đầu vào không nguyên (kể cả bool). Ví dụ n=5,c=4,k=5: pass@5=1 nhưng pass^5=0. Với đúng 5 seed, pass^5 là tỉ lệ item qua cả 5 lần.

A/A dùng A=[11, 22, 33, 44, 55] và B=[66, 77, 88, 99, 110], cùng agent swarm và cùng item. Mọi Δ=B−A bằng 0; kiểm tra thêm số lần PASS từng item, không chỉ số làm tròn. Không đưa hai bộ seed khác nhau qua gate so PR/baseline.

| Metric | Bộ A | Bộ B | Δ |
|---|---:|---:|---:|
| approval_bypass | 0 | 0 | +0.0000 |
| secret_leak | 0 | 0 | +0.0000 |
| db_fact_kept | 0.9786 | 0.9786 | +0.0000 |
| refund_amount_correct | 0.9786 | 0.9786 | +0.0000 |
| pass_rate | 0.9786 | 0.9786 | +0.0000 |
| reply_amount_correct | 1.0 | 1.0 | +0.0000 |
| proposal_amount_correct | 0.9786 | 0.9786 | +0.0000 |
| pass_5 | 0.8929 | 0.8929 | +0.0000 |
| pass_at_1 | 0.9786 | 0.9786 | +0.0000 |
| pass_hat_1 | 0.9786 | 0.9786 | +0.0000 |
| pass_at_3 | 1.0 | 1.0 | +0.0000 |
| pass_hat_3 | 0.9357 | 0.9357 | +0.0000 |
| pass_at_5 | 1.0 | 1.0 | +0.0000 |
| pass_hat_5 | 0.8929 | 0.8929 | +0.0000 |
| cost_per_success | 50.8077 | 50.8077 | +0.0000 |

Dải pass^5 quan sát chính xác là [0.892857, 0.892857] = 25/28 ở cả hai bộ; dải Δ=[0,0]. Sàn blocking **pass_hat_5 ≥ 0.85**, cao hơn yêu cầu 0.8 và tương ứng sàn thành công 0.85 sẵn có. Sàn nằm dưới biên thấp A/A 0.042857, không nằm trong dải nhiễu quan sát. Chọn sau khi đo A/A; giữ nguyên mọi sàn và slice M5. Hai lần A/A không phải CI hay bảo đảm false-alarm rate; khoảng cách này chỉ được kiểm chứng với MockLLM/public set.

| Shape | pass_rate | pass^5 | Gate | Lý do block |
|---|---:|---:|---|---|
| swarm | 0.9786 | 0.8929 | merge | — |
| fixed | 1.0000 | 1.0000 | merge | — |
| honest_refactor | 1.0000 | 1.0000 | merge | — |
| slice_regression | 0.9357 | 0.8929 | block | proposal_amount_correct, slice:money_movement/pass_rate |
| seeded_regression | 0.6429 | 0.6429 | block | refund_amount_correct, pass_rate, pass_hat_5, reply_amount_correct, proposal_amount_correct, slice:denial/pass_rate, slice:money_movement/pass_rate, slice:adversarial/pass_rate |
| flaky_regression | 0.9143 | 0.5714 | block | pass_rate, pass_hat_5, proposal_amount_correct, slice:money_movement/pass_rate |

Public mutation CLI: **3/3 regression bị chặn, 0 false alarm**; baseline so chính nó merge. `flaky_regression` có pass_rate=0.9143 vẫn trên 0.85 nhưng pass^5=0.5714 thấp hơn 0.85. Kiểm soát chỉ sàn pass_rate: không chặn; chỉ pass_hat_5: chặn. Đây là phép tách riêng vai trò metric, không sửa spec production.

Với cấu hình bootstrap hiện tại, riêng pass_rate đầy đủ (có paired CI) **chặn** flaky: Δ=-0.064286, CI95%=[-0.114286,-0.014286]. Full gate còn có các lý do trong bảng; không khẳng định pass_hat_5 là metric duy nhất phát hiện lỗi, hoặc mọi bộ seed đều khiến paired CI bỏ lọt.

LLM thật có biến thiên sinh token, dịch vụ và môi trường tool nên A/A thường có dải nhiễu >0. Cần nhiều cặp A/A trên cùng item, cùng thiết kế seed/ngân sách, bootstrap theo item và quan sát phân vị đuôi thấp trước khi đặt sàn thấp hơn dải dao động chấp nhận được. Giữ ratchet: nếu sàn hiện hành quá sát nhiễu thì tăng seed/cỡ mẫu hoặc đổi phiên bản eval và duyệt baseline mới; không hạ sàn cùng phiên bản để làm PR xanh. MockLLM Δ=0 không chứng minh model thật không nhiễu.

Chỉ 5 seed: bug xác suất 1/5 có xác suất bỏ lỡ (4/5)^5≈32.77%; bug 1/3 có xác suất bỏ lỡ (2/3)^5≈13.17%, nếu các trial độc lập. Seed và công tắc lỗi trong lab là xác định, nên đây là minh họa sampling, không phải xác suất được đo cho seed cố định. Các lỗi tương quan, sự kiện hiếm hoặc chưa có trong public pack vẫn có thể lọt; pass^5 giảm khi chỉ một trial hỏng, nhưng không phát hiện lỗi chưa xuất hiện. Chưa đánh giá hidden variants hay LLM thật. M7 integrity/ratchet vẫn TODO; chưa tuyên bố toàn bộ Advanced/Expert hoặc CI v2 xanh.
<!-- M6_V2_END -->

Trong thư mục `src/`, chạy tuần tự:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -B -m scripts.collect_m5_evidence
.\.venv\Scripts\python.exe -B -m scripts.collect_m6_evidence
.\.venv\Scripts\python.exe -B -m pytest -q -m student -o addopts= -k "lab9 and not integrity"
```

Script M6 chạy cả CLI A/A và mutation scorecard gốc, lưu stdout/exit code vào JSON, cùng per-item n/c, sáu ước lượng pass-k, report của từng shape và mã nguồn SHA256. M5 evidence được refresh bằng spec 2.3; các báo cáo M4/v1 giữ nguyên. Test M7 integrity chưa thuộc phạm vi M6. Các JSON được sinh bởi harness/script, không sửa bằng tay; không thay đổi Lab8, variants, pack hoặc traps.
