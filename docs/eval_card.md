# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:**
- **Phiên bản:** code (commit) … · eval set v1 (sha …) · metric_spec … · grader (commit) … · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json
- **Metric & ngưỡng:** (trích metric_spec.yaml)
- **Kết quả baseline vs PR:** bảng + paired CI
- **Judge:** tone_ok κ=…, P=…, R=…; helpful bị loại vì …
- **Trace case:** link `docs/trace_case.md`, bước sai đầu tiên, regression test
- **Gate owner:** ai xử lý khi gate exit 1
- **Phạm vi pilot:** …
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item, judge replay; không đo trên người dùng thật
- **Khi nào tăng eval-set version:** …

## Bổ sung v2 — M5/M6

- **Dữ liệu:** eval set v2 gồm 28 item (14 public v1 + 14 adversarial), 5 seed/item; SHA `b95000ad87f9`. Mechanism trong pack được ánh xạ sang FM-02…FM-09 qua `config/fm_map.yaml`; `evalset --v2` báo 0 problem(s).
- **Slice M5:** `money_movement`, `adversarial`, `denial` đều có sàn `pass_rate` 0.90 và blocking. Trên baseline swarm, ba slice lần lượt đạt 1.0000, 0.9714, 0.9455. `slice_regression` đạt pass_rate tổng 0.9357 (trên sàn chung 0.85), nhưng `money_movement` chỉ 0.8500 nên bị chặn bởi `slice:money_movement/pass_rate`. CI paired của slice là [−0.300, +0.000], chạm 0; sàn slice mới là lý do chặn.
- **Nhiễu A/A M6:** chạy swarm trên seed 11,22,33,44,55 và 66,77,88,99,110; `pass_hat_5` đều 0.8929, Δ = 0 trong MockLLM. Sàn blocking 0.80 nằm dưới hai lần A/A nhưng trên `flaky_regression` 0.5714. Với model thật, dải nhiễu có thể rộng hơn; phải đo A/A mới trước khi giữ nguyên sàn.
- **Độ tin cậy:** `pass@k` là xác suất ít nhất một lần đúng, còn `pass^k` (`pass_hat_k`) đòi cả k lần đúng. `flaky_regression` vẫn có pass_rate 0.9143 nhưng `pass_hat_5` chỉ 0.5714. Một lỗi xuất hiện ở 1/3 seed không được bảo đảm phát hiện ổn định chỉ với 5 seed; cần tăng số seed và đánh giá lại độ bất định, không chỉnh ngưỡng theo một lần chạy thuận lợi.
- **Giới hạn:** các kết quả trên dùng MockLLM, pack công khai và report local; chưa chứng minh hiệu quả với người dùng hoặc model thật.

## Bổ sung M7 — tính toàn vẹn của gate

- `integrity_check` từ chối metric NaN/inf hoặc không khớp các dòng, grader crash/giá trị trống, số dòng hoặc cặp `(item_id, seed)` sai, dòng trùng, đổi nhãn slice và spec cùng phiên bản bị nới ngưỡng hay bỏ metric/slice chặn.
- Bốn trap công khai (`evaluator_errors_as_nan`, `dropped_failing_rows`, `cherry_picked_seeds`, `loosened_spec`) đều bị gate trả `exit 1 — blocked: integrity`; lệnh tổng hợp `lab9.traps` trả exit 0 vì 4/4 trap bị chặn.
- Scorecard biến thể công khai đạt 3/3 regression bị chặn và 0 báo nhầm trên `fixed`, `honest_refactor`. Đây là bằng chứng trên trap công khai, không bảo đảm bao phủ mọi cách sửa report hay spec ở bộ chấm ẩn.
