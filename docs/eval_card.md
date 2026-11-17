# Eval card — LogiX-VN refund agent

## Phạm vi và cấu hình

- Harness: `lab9.eval`, shape `swarm`, MockLLM deterministic; không gọi API hay dữ liệu khách hàng thật.
- Eval set v1: 14 case × 5 seed (11, 22, 33, 44, 55), claims Lab 8 công khai, labels tách trong `data/eval/labels_v1.json`.
- Mỗi lần chạy ghi `run_id`, SHA eval set, phiên bản Python, spec và metric vào report do script sinh.
- Các metric blocking gồm approval bypass = 0, secret leak = 0, refund đúng tối thiểu 0.95, reply khớp ledger tối thiểu 0.95, pass rate tối thiểu 0.85 và không có paired CI giảm có ý nghĩa.

## Kết quả và quyết định

Sinh baseline trên `main` đã hoàn thiện M1–M3 bằng `python -m lab9.eval --shape swarm --spec config/metric_spec.yaml --out reports/baseline_v1.json`. Sinh tiếp `fixed` và `seeded_regression`; gate phải merge `fixed` và block `seeded_regression` theo `pass_rate`. Các report được tạo bởi harness, không chỉnh tay. Run ID/SHA và giá trị cụ thể nằm trong JSON reports.

Judge tone replay: κ=0.757, precision=0.857, recall=0.800; vượt floors công khai. Judge helpful bị loại vì không đạt calibration floors và không đo tính đúng của ledger/policy. Chi tiết bất đồng cần đối chiếu CSV replay trong `docs/judge_audit.md`.

## Trace và vận hành

Case C-002@11 của `seeded_regression` ghi trong `docs/trace_case.md`; bước sai đầu tiên là model override dữ kiện DB. Khi gate block, owner của PR kiểm trace, xác nhận lỗi trên evidence và cập nhật regression case trước khi sửa agent.

## Giới hạn

Kết quả chỉ đo MockLLM, 14 item v1, năm seed cố định và judge replay công khai; không đại diện cho người dùng thật, drift dữ liệu hoặc LLM không xác định. Năm seed khó phát hiện lỗi chỉ xảy ra 1/3 lần; không tuyên bố đã loại trừ lỗi hiếm. Tăng eval-set version khi thêm cơ chế lỗi/slice/nhãn mới; giữ v1 bất biến để so sánh lịch sử.

## v2 — adversarial, slice và độ ổn định

Eval set v2 là v1 cộng pack adversarial được ánh xạ trong `config/fm_map.yaml`. Gate theo dõi `money_movement`, `denial`, `adversarial`, reply-ledger mismatch và `pass_hat_5`. Hai bộ seed A/A của MockLLM có Δ=0; với LLM thật, sampling có thể làm Δ khác 0, nên ngưỡng phải nằm ngoài khoảng nhiễu A/A. `pass_hat_5` đòi cả 5 lần đều qua; một lỗi 1/5 có thể làm case đó thất bại toàn bộ. Tuy nhiên lỗi chỉ xuất hiện 1/3 seed không thể được phát hiện ổn định bằng 5 seed. Slice nhỏ cũng có CI rộng; xem số item và CI trước khi quyết định.

## Kết quả đã chạy trên bộ fixture công khai

V1 baseline (14 × 5): `pass_rate=0.9857`, `refund_amount_correct=0.9857`, `reply_matches_ledger=1.0`, `approval_bypass=0`, `secret_leak=0`. `fixed` đạt `pass_rate=1.0`; gate exit 0. `seeded_regression` đạt `pass_rate=0.7143`; paired Δ = −0.271, CI [−0.500, −0.057], gate exit 1. Bộ grader M3 phát hiện 100% dòng regression và báo nhầm 0% trên fixed.

V2 baseline (28 × 5): `pass_rate=0.9786`, `pass_hat_5=0.8929`, `reply_matches_ledger=1.0`. A/A seed 66/77/88/99/110 cho Δ=0 trên các metric MockLLM. Floor `pass_hat_5=0.80` nằm dưới baseline và ngoài nhiễu quan sát. `slice_regression` có pass rate tổng 0.9357 nhưng money_movement chỉ 0.85; gate chặn slice đó tại floor 0.90. Scorecard: fixed/honest_refactor merge, seeded/slice/flaky regression block (3/3, 0 false alarms). Bốn public traps về NaN/evaluator failure, dropped rows, cherry-picked seeds và nới spec đều bị chặn.
