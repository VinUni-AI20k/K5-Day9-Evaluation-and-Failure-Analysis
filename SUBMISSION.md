# Nộp bài (bài cá nhân, hạn nộp theo ca làm bài)
1. Commit các report sinh bằng script: trong `src/` chạy `git add -f reports/*.json` (`.gitignore` bỏ qua `src/reports/`, không có `-f` thì report không lên repo).
2. Mở PR `starter/d09` → `main` **trong bản fork của bạn**, không mở vào repo gốc. Dán output gate exit 1 của `seeded_regression` vào mô tả PR.
3. Job `eval-gate` xanh thì **merge PR vào `main`**. Giảng viên chấm nhánh `main` của bản fork; commit sau hạn của ca không tính.
4. Dán **link repo fork** (`K5-L3A-DAY09-HoVaTen-MSSV-EvaluationandFailureAnalysis`) lên LMS.

Làm thêm Advanced/Expert sau buổi: tiếp tục trên nhánh, mở PR mới rồi merge lại trước hạn.

## Core (nên xong trước 17:00)
- [x] `src/lab9/{stats,graders,evalset}.py` đã hoàn thành TODO M1–M4
- [x] `src/data/eval/eval_set_v1.jsonl` có `failure_modes`, `labels_v1.json` tách riêng
- [x] `docs/failure_taxonomy.md`, `docs/trace_case.md` (1 case + regression test), `docs/judge_audit.md`, `docs/eval_card.md`, `docs/PRD_v1.1.md`
- [ ] `src/reports/baseline_v1.json`, `eval_fixed.json`, `eval_seeded_regression.json` (sinh bằng script, commit bằng `git add -f`)
- [x] `harness_map.yaml` có section `eval` (mẫu: `src/harness_map.eval.yaml`)
- [ ] Job `eval-gate` xanh; dán output gate exit 1 của `seeded_regression` vào mô tả PR

## Advanced / Expert (tới hạn nộp)
- [x] `config/fm_map.yaml`, `config/metric_spec_v2.yaml` (slices, `pass_hat_5`, metric FM-08), `stats.pass_at_k/pass_hat_k`, `gate.slice_check`, `gate.integrity_check`
- [x] `src/data/eval/eval_set_v2.jsonl` + `labels_v2.json` (sinh bằng `evalset --v2 --build`)
- [ ] `src/reports/baseline_v2.json` (sinh bằng script, commit bằng `git add -f`) → job `eval-gate-v2` chạy và xanh
- [ ] Mô tả PR: output `lab9.mutation` (scorecard + `--aa`) và 4 dòng `exit 1` của các trap
- [x] `docs/eval_card.md` thêm mục v2: ngưỡng chọn từ A/A, slice nào bắt lỗi nào, và giới hạn cỡ mẫu (bug 1/3 seed không phát hiện ổn định với 5 seed)

## Trạng thái chuẩn bị nộp ngày 2026-11-18

Đã hoàn thiện code, dữ liệu v1/v2, tài liệu và report trên local. Nội dung mô tả PR đã chuẩn bị trong `docs/PR_description.md`. Danh sách report và lệnh tái tạo ở `src/reports/README.md`.

Các bước còn chờ gồm force-add report, commit/push, mở PR trong fork, xác nhận hai job CI xanh, merge vào main và nộp link fork trên LMS. Các ô gắn với commit/CI/PR được giữ trống cho tới khi có kết quả thực tế.
