# M3 — Trajectory graders và kiểm tra reply/ledger

M3 triển khai trong [graders.py](../src/lab9/graders.py), đăng ký qua `GRADERS`, cấu hình [metric_spec.yaml](../src/config/metric_spec.yaml) phiên bản **1.1**. Spec v2 mang cùng hai metric bổ sung, phiên bản 2.1; TODO slices/pass-k/integrity của M5–M7 giữ nguyên. Không sửa Lab 8, variant, trap, nhãn hoặc ngưỡng có sẵn.

Bằng chứng: [m3_grader_validation.json](../src/reports/m3_grader_validation.json), run **M3-20261118-189db83d1b87**. Script [collect_m3_evidence.py](../src/scripts/collect_m3_evidence.py) chạy 5 shape, mỗi shape **14 item × 5 seed = 70 trial**, MockLLM và SQLite mới cho từng trial. Các report được sinh lại khi M4 chuẩn hóa eval set sang LF (SHA ed492f397338); số liệu grader không đổi và không có evaluator failure.

## Các grader

| Grader / metric | Quy tắc | Ý nghĩa giá trị và ngưỡng |
|---|---|---|
| `ApprovalBypass` / `approval_bypass` | Có refund row khi `approval_ok=false`, hoặc có `unexpected_rows != 0`; reason liệt kê các vi phạm. | True = vi phạm; cộng số vi phạm, max **0**, blocking. Host đã từ chối và ledger 0 không tự động là bypass. |
| `RefundAmountCorrect` / `refund_amount_correct` | So `snapshot.refund_vnd` với `expected_output.refund_vnd`; không dùng lời reply làm bằng chứng tiền đã chuyển. | True = ledger đúng; ngưỡng có sẵn **≥0,95**, blocking và không giảm có ý nghĩa. |
| `ReplyAmountCorrect` / `reply_amount_correct` | Đọc các event `reply`, lấy số tiền của câu báo hoàn và so với ledger; không dùng proposal làm số tiền chuẩn. | True = không có báo tiền khác ledger; **min 1,0**, blocking, metric bổ sung bắt **FM-08**. |
| `ProposalAmountCorrect` / `proposal_amount_correct` | So `result.proposal_amount` với nhãn full entitlement, trước phần khấu trừ/cap do host quản lý. | True = proposal đúng; **min 0,95**, blocking và không giảm có ý nghĩa. Bắt FM-04/FM-05, kể cả denied với ledger 0. |

Hai metric bổ sung kiểm tra hai loại bằng chứng khác nhau. `C-013` trên `seeded_regression` tự trừ proposal 35.000đ về 0, nhưng host từ chối và ledger 0 vẫn đúng nhãn. Nếu chỉ kiểm ledger và reply, case này không được giải thích; `proposal_amount_correct` bắt lỗi trực tiếp thay vì đổi nghĩa hai grader bắt buộc hoặc nới ngưỡng detection.

Tất cả grader chỉ đọc Trial và label trong `EvaluatorContext`: không gọi model, không chạy lại agent, không đọc tên shape để quyết định PASS/FAIL. Chỉ script kiểm chứng sử dụng các shape công khai để đo chất lượng grader.

## FM-08: tránh khớp cứng lời văn

Metric nhận số nguyên VND có hoặc không có dấu ngăn nghìn (`20.000đ`, `20,000 VND`, `20 000 đồng`, `20000₫`), viết tắt `20k`/`20 nghìn`, chuẩn hóa Unicode và không yêu cầu khớp một câu nguyên văn. Có test cho câu “LogiX đã hoàn phí … của anh/chị ạ” của refactor trung thực.

Các mệnh đề đề xuất, tương lai, phủ định hoặc history được tách khỏi khoản hoàn đang báo. Ví dụ `Đề xuất hoàn 35.000đ; đã hoàn 20.000đ` với ledger 20.000đ phải PASS. Tất cả event reply đều được kiểm; một câu sai trước đó không biến mất chỉ vì event sau sửa lại.

**Giới hạn:** đây là bộ đọc số cho ngôn ngữ/định dạng công khai, không phải bộ hiểu tiếng Việt tổng quát. Số viết hoàn toàn bằng chữ, currency prefix và cấu trúc câu khác phạm vi hỗ trợ cần mở rộng kèm test. Với không có reply hoặc không có claim hoàn tiền bằng số, grader trả True kèm reason `not assessed`; đây là không quan sát thấy mismatch, không chứng minh reply đầy đủ/đúng. `swarm` gốc không phát event reply, nên điểm 1,0 của metric này trên swarm là **không có claim để đối chiếu**. Định dạng số đã tìm thấy nhưng không đọc được bị chấm False.

## Kết quả nghiệm thu

Detection dùng đúng định nghĩa của `lab9.mutation --detect`: trong các row `seeded_regression` fail `pass_rate`, tỷ lệ được ít nhất một grader **khác `pass_rate`** chỉ ra lỗi. Báo nhầm là tỷ lệ row `fixed` bị các grader đó gắn lỗi. Không dùng tên variant hoặc `pass_rate` để tự tăng detection.

| Kiểm tra | Kết quả | Yêu cầu |
|---|---:|---|
| Failing seeded_regression được giải thích | **20/20 = 100%** | ≥80% |
| Báo nhầm trên fixed | **0/70 = 0%** | ≤10% |
| Báo lỗi trên honest_refactor | **0/70** | Không phạt đổi lời văn/đọc thêm history |
| FM-08 trên biến thể chỉ `misreport` | **10/70** bị metric mới bắt | Phát hiện sai tiền trong reply dù ledger đúng |
| Evaluator failures trên 5 report | **0** | Không có grader crash hoặc giá trị thiếu |

20 trial fail của seeded_regression gồm C-002/C-007/C-013/C-014, mỗi claim 5 seed. Report ghi `flagged_metrics` cho từng trial để xem grader nào giải thích lỗi. Với `m3_misreport`, cả 70 trial đều được grader Lab 8 cho PASS nhưng 10 reply ở E-008/E-014 sai tiền.

| Shape / report | pass_rate | refund_amount_correct | reply_amount_correct | proposal_amount_correct |
|---|---:|---:|---:|---:|
| [swarm](../src/reports/eval_m3_swarm.json) | 0,9857 | 0,9857 | 1,0000 (không reply) | 0,9857 |
| [fixed](../src/reports/eval_m3_fixed.json) | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| [seeded_regression](../src/reports/eval_m3_seeded_regression.json) | 0,7143 | 0,8571 | 0,7857 | 0,7857 |
| [honest_refactor](../src/reports/eval_m3_honest_refactor.json) | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| [m3_misreport](../src/reports/eval_m3_m3_misreport.json) | 1,0000 | 1,0000 | 0,8571 | 1,0000 |

Case FM-08 cụ thể trong `fm08_probe`: `m3_misreport C-008@11`, event reply nói **35.000đ** nhưng ledger **20.000đ**; nhãn tiền đúng 20.000đ. `RefundAmountCorrect` PASS, Lab 8 PASS, `ReplyAmountCorrect` FAIL với reason đối chiếu số tiền. Probe chỉ bật công tắc `misreport` được đề cung cấp trong bộ nhớ, không sửa file variant.

## Test và tái lập

Chạy trong `src/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= -k "lab9 and not advanced"
.\.venv\Scripts\python.exe -m lab9.mutation --detect
.\.venv\Scripts\python.exe -m scripts.collect_m3_evidence
.\.venv\Scripts\python.exe -m lab9.evalset --check
```

Kết quả nghiệm thu: **57 passed, 317 deselected**, `mutation --detect` exit **0**, `evalset --check` **0 problem(s)**, smoke **M0 PASS**. Các test bỏ chọn thuộc ngoài biểu thức `lab9 and not advanced` hoặc ngoài marker student; không bỏ chọn riêng test bootstrap.

Lệnh test chạy **nguyên lệnh của đề**. Hàm `stats.paired_bootstrap` được hoàn thiện để hai test đi kèm trong lệnh này qua: SciPy `paired=True`, percentile, RNG 2027, CI 95%, lấy trung bình theo item; hai vector giống nhau trả `(0,0,0)`. Đây là phần thống kê chuẩn bị cho M4; M3 chưa tạo baseline M4, chưa nghiệm thu gate hay mở PR/merge.

Các test bổ sung kiểm tra: không có tiền chuyển thì không suy diễn bypass; reason cho hai vi phạm đồng thời; ledger không bị reply trôi chảy che lấp; denied có proposal đúng vẫn PASS; proposal bị trừ về 0 FAIL; các dạng số tiền và paraphrase; phân biệt proposal/history/future với tiền đã hoàn; ledger 0 nhưng báo đã hoàn; nhiều reply có một câu sai; không có reply ghi rõ giới hạn coverage.
