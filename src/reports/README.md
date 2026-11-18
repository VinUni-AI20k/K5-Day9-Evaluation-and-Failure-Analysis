# Báo cáo nộp Lab 9 — Đào Văn Hiệp

Các JSON được sinh bằng lệnh trong thư mục `src/`. Bộ seed chuẩn là 11,22,33,44,55.

| File | Nội dung | Lệnh tạo |
|---|---|---|
| baseline_v1.json | Swarm, 14 item v1 | python -m lab9.eval --shape swarm --out reports/baseline_v1.json |
| eval_fixed.json | Đối chứng Core | python -m lab9.eval --shape fixed |
| eval_seeded_regression.json | Regression Core | python -m lab9.eval --shape seeded_regression |
| baseline_v2.json | Swarm, 28 item v2 | python -m lab9.eval --shape swarm --spec config/metric_spec_v2.yaml --out reports/baseline_v2.json |
| eval_slice_regression.json | Regression ở slice | python -m lab9.eval --shape slice_regression --spec config/metric_spec_v2.yaml --out reports/eval_slice_regression.json |
| eval_flaky_regression.json | Regression chập chờn | python -m lab9.eval --shape flaky_regression --spec config/metric_spec_v2.yaml --out reports/eval_flaky_regression.json |
| eval_fixed_v2.json | Đối chứng v2 | python -m lab9.eval --shape fixed --spec config/metric_spec_v2.yaml --out reports/eval_fixed_v2.json |
| eval_honest_refactor_v2.json | Refactor hợp lệ | python -m lab9.eval --shape honest_refactor --spec config/metric_spec_v2.yaml --out reports/eval_honest_refactor_v2.json |
| traps/*.json | Bốn report có sửa đổi để kiểm tra integrity | python -m lab9.traps --pr reports/eval_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml |

Output gate của từng trap nằm trong `traps/gate_output.txt`. Kết quả A/A và scorecard được ghi trong `../../docs/eval_card.md` và `../../docs/PR_description.md`.

Thư mục reports bị gitignore. Khi chuẩn bị commit cần dùng `git add -f src/reports/README.md src/reports/*.json src/reports/traps/*.json src/reports/traps/*.yaml src/reports/traps/gate_output.txt` từ gốc repo. Mọi JSON được tạo bằng script. Các báo cáo này dùng để kiểm tra lại bằng các lệnh ở trên.
