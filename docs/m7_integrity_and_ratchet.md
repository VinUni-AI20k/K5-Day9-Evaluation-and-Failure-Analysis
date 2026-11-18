# M7 — Chống gian lận eval

<!-- M7_V2_BEGIN -->
## v2 — M7: integrity và policy ratchet

Evidence **M7-20261118-f1d606d5fd5b**, [JSON đầy đủ](../src/reports/m7_integrity_validation.json). Ngày 2026-11-18 UTC+7; MockLLM, spec 2.3, SHA eval-set 088a201ad90e, 28 item × 5 seed. Test: `172 passed, 305 deselected in 2.54s`.

Gate kiểm tra cả PR và baseline trước khi chấm điểm: metric hữu hạn, đủ grade ở từng row; không chấp nhận None/string/NaN/∞; không có evaluator_failures. Manifest items/seeds phải hợp lệ, seeds duy nhất; đủ tích Descartes item × seed, không dòng trùng kể cả khi tổng số dòng không đổi. Hai report phải có cùng cặp (item_id, seed), cùng tag slice cho từng item; tag cũng phải nhất quán giữa các seed. Thứ tự row, seed hoặc tag không ảnh hưởng. Aggregate của metric được chấm và metric dẫn xuất trong spec phải khớp kết quả tính lại từ row, theo quy tắc làm tròn của harness. JSON/metadata lỗi có verdict INTEGRITY, không dùng traceback làm bằng chứng PASS.

Ratchet đối chiếu `--base-spec`: cùng eval_set_version thì không giảm min, tăng max/max_increase, bỏ threshold/metric/slice, bỏ blocking hoặc no_significant_drop. Không dùng tăng metric_spec_version hoặc xóa eval_set_version để lách. Cho phép giữ/siết sàn và thêm kiểm tra. Đổi eval_set_version chỉ mở vòng thiết kế chính sách mới; gate vẫn từ chối so report khác eval_set_sha, cần baseline cùng tập. Không nới bất kỳ sàn M5/M6 nào.

| Trap / probe | CLI exit | Một lý do thực tế |
|---|---:|---|
| evaluator_errors_as_nan | 1 | INTEGRITY PR: row ('E-014', 11) has missing/non-finite grade pass_rate |
| dropped_failing_rows | 1 | INTEGRITY PR: row count 131 != items x seeds (140) |
| cherry_picked_seeds | 1 | INTEGRITY PR: manifest seeds differ from the metric spec |
| loosened_spec | 1 | INTEGRITY ratchet metrics ('db_fact_kept',): min loosened or removed |
| duplicate_same_length | 1 | INTEGRITY PR: duplicate (item_id, seed) ('E-001', 11) |
| evaluator_failure_on_green | 1 | INTEGRITY PR: evaluator_failures is missing, invalid or non-empty |
| slice_relabel | 1 | INTEGRITY PR and baseline per-item slice tags differ |
| forged_summary | 1 | INTEGRITY PR: aggregate pass_rate disagrees with row grades |

Bốn trap công khai đều có dòng INTEGRITY và `exit 1 — blocked: integrity`. Bốn probe bổ sung được script sinh từ fixed xanh, không sửa tay JSON. `evaluator_errors_as_nan` có thể không tạo NaN trong mọi cấu hình; vẫn bị chặn do grade None. Không dựa vào tên trap/variant để ra quyết định.

Baseline so chính nó, swarm PR mới, fixed và honest_refactor đều qua gate. Scorecard gốc chạy lại từ trial: **3/3 regression bị chặn, 0 false alarm**. A/A mới: mọi Δ=0. Fresh swarm v1 qua gate và ci_check với baseline Core cũ. CLI, stdout/exit code và source/input hashes được lưu trong JSON.

Workflow v2 fetch lịch sử và lấy spec từ commit base của PR bằng `git show`, đưa vào cả gate swarm và mutation. workflow_dispatch dùng spec tại github.sha. CI chạy toàn bộ test LAB09 và yêu cầu từng trap CLI trả exit 1 kèm INTEGRITY; một exception hay một metric khác đỏ không được coi là bằng chứng integrity. Đã chạy kiểm tra tương đương local, kể cả so với spec từ nhánh main local; chưa chạy GitHub Actions từ xa hay kiểm tra branch protection.

Giới hạn: chưa chạy bộ chấm/variant/trap ẩn của giảng viên, không bảo đảm điểm Expert. Duplicate và evaluator_failures trên run xanh đã có test/probe riêng, nhưng gate không xác thực chữ ký trace hoặc nguồn gốc các grade. Kẻ có quyền thay đồng bộ row, aggregate, baseline hoặc grader có thể tạo report nhất quán giả; cần trusted baseline, replay harness trên CI, review thay đổi grader/workflow và bảo vệ nhánh. Spec gốc phải đến từ nguồn tin cậy; tự đưa cùng spec đã nới vào cả --spec và --base-spec không tạo được bảo đảm ratchet. M5/M6 vẫn chỉ là public MockLLM, 28 item và 5 seed; giới hạn sampling của M6 vẫn áp dụng.
<!-- M7_V2_END -->

Trong thư mục `src/`:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\.venv\Scripts\python.exe -B -m scripts.collect_m7_evidence
```

Script chạy tuần tự để hạn chế dùng bộ nhớ. Các report M5/M6 được giữ làm evidence lịch sử; M7 ghi report swarm mới, trap/probe và validation riêng bằng script. `reports/traps/loosened_spec.spec.yaml` được tạo bởi lab9.traps, chỉ dùng đối chứng chống nới ngưỡng. Không sửa Lab8, variants, mutation hoặc traps để qua kiểm tra. Việc push/PR/merge đang được để riêng theo yêu cầu người dùng.
