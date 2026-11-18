# Judge audit — M2

Nguồn: `src/data/eval/judge_tone_public.csv` và `judge_helpful_public.csv` (100 dòng mỗi file). Backend **replay**, không gọi LLM/API và không thay nhãn CSV. Bằng chứng sinh bằng script: [m2_judge_calibration.json](../src/reports/m2_judge_calibration.json), run **M2-20261118-587c86be2a96**; mã tạo report: [collect_m2_evidence.py](../src/scripts/collect_m2_evidence.py).

## Calibration trên nhãn gốc

Lớp dương là **FAIL**: TP là lỗi người đánh FAIL và judge tìm được; FN là lỗi judge bỏ sót. FLOORS phải đồng thời đạt κ ≥ 0,6, Precision ≥ 0,8, Recall ≥ 0,7. κ không xác định gây `ValueError` trong stats, được calibration chuyển thành NaN và **không đạt** floors.

| Tiêu chí | n | TP / FP / FN / TN | κ | Precision | Recall | Đạt FLOORS? | Quyết định |
|---|---:|---|---:|---:|---:|---|---|
| tone_ok | 100 | 24 / 4 / 6 / 66 | 0,757 | 0,857 | 0,800 | PASS cả ba | Dùng cho tone trong phạm vi replay đã đo. |
| helpful | 100 | 9 / 0 / 21 / 70 | 0,375 | 1,000 | 0,300 | FAIL κ và Recall | **Loại khỏi gate**; sửa rubric và calibration lại trước khi dùng. |

Tone bỏ sót 6/30 lỗi, báo nhầm 4/70 case không lỗi. Helpful có precision hoàn hảo vì 9 lần báo FAIL đều đúng, nhưng **bỏ sót 21/30 lỗi (70%)**. Không dùng riêng precision hoặc văn phong lịch sự để kết luận judge đáng tin.

Trong 21 bất đồng của helpful có 18 case `human_failure=sai tiền` và 3 case `sai xưng hô`. Các nhãn lỗi này đến từ CSV, không phải suy đoán chỉ từ độ dài reply.

## Hiệu chỉnh tỉ lệ lỗi (Rogan–Gladen)

`p_true = clip((p_observed + specificity - 1) / (sensitivity + specificity - 1), 0, 1)`, với sensitivity = Recall và specificity = TN/(TN+FP).

| Judge | Lỗi quan sát từ judge | Sensitivity | Specificity | Tỉ lệ lỗi hiệu chỉnh | Tỉ lệ FAIL nhãn người |
|---|---:|---:|---:|---:|---:|
| tone | 0,280 | 24/30 = 0,800 | 66/70 ≈ 0,942857 | 0,300 | 0,300 |
| helpful | 0,090 | 9/30 = 0,300 | 70/70 = 1,000 | 0,300 | 0,300 |

Hiệu chỉnh ước lượng tỉ lệ lỗi tổng thể; không sửa quyết định từng case và không biến helpful thành judge đủ chuẩn gate. Số hiệu chỉnh bằng tỉ lệ nhãn người vì sensitivity/specificity được đo trên chính bộ calibration, chưa chứng minh chất lượng trên dữ liệu mới. Mẫu số bằng 0 bị từ chối thay vì gán một tỉ lệ đẹp.

## Audit bất đồng của tone (10/10 case)

Các nhận định dựa trên reply và `note` của dữ liệu công khai; đây là phân tích lại bằng chứng sẵn có, không phải đợt thu thập nhãn người độc lập. Ngữ cảnh chỉ có trong note được nêu rõ. Không sửa CSV để làm tăng điểm calibration.

| Case | Judge nói | Người nói | Ai đúng / căn cứ | Sửa rubric hoặc quy trình cụ thể |
|---|---|---|---|---|
| H-008 | PASS | FAIL | Người: “Em…anh…nha…check” suồng sã theo chuẩn CS LogiX. | Thêm negative example; yêu cầu xưng hô anh/chị và giọng trang trọng, không đánh đồng thân thiện với phù hợp. |
| H-017 | PASS | FAIL | Người theo note về khách lớn tuổi: “bạn ơi…rồi nha” không phù hợp; tuổi không suy ra từ reply. | Cung cấp ngữ cảnh xưng hô; khi thiếu thì dùng chuẩn anh/chị, không đoán tuổi. |
| H-029 | PASS | FAIL | Người: “không cần nhắn thêm” ra lệnh dù mở đầu “Dạ, vui lòng”. | Đọc toàn câu; thêm FAIL example với lời mở đầu lịch sự nhưng nội dung làm khách im lặng. |
| H-042 | FAIL | PASS | Người: câu ngắn nhưng lịch sự, đủ tiền/đơn/thời gian; note nói judge đòi xin lỗi. | Không bắt buộc từ “xin lỗi” ở mọi câu; thêm positive example ngắn đủ ý. |
| H-051 | FAIL | PASS | Người theo note: LogiX cho phép từ “refund”; câu vẫn lịch sự. | Whitelist từ được phép, không FAIL chỉ vì một từ tiếng Anh. |
| H-063 | PASS | FAIL | Người theo note: “sẽ hoàn thêm” hứa ngoài kết quả hệ thống; reply không chứng minh có approval cho khoản thêm. | Không hứa ngoài host; nội dung tiền đối chiếu ledger/approval bằng code, không đánh PASS chỉ vì “Dạ…ạ”. |
| H-070 | PASS | FAIL | Người: emoji “😂😂” không phù hợp phản hồi khiếu nại theo rubric này. | Thêm negative example emoji cười trong khiếu nại; không coi emoji luôn thân thiện. |
| H-081 | FAIL | PASS | **Judge đúng theo adjudication note**: người đọc nhầm ticket; reply riêng lẻ không đủ kiểm chứng độc lập việc đọc nhầm. | Ghi lỗi nhãn cần đối chiếu ticket gốc; không âm thầm đổi CSV. Khi nhãn mới được duyệt, version tập nhãn rồi calibration lại. |
| H-088 | FAIL | PASS | Người theo note: lặp “Dạ, dạ” là lỗi gõ nhỏ, không làm câu thiếu lịch sự. | Tách lỗi trình bày nhẹ khỏi vi phạm tone; thêm positive example lặp một từ. |
| H-094 | PASS | FAIL | Người theo note: dịch mất dấu “Da…da hoan…xin loi” không đạt chuẩn CS LogiX. | Nêu chuẩn tiếng Việt có dấu và thêm negative example; không chỉ tìm từ gợi lịch sự. |

## Audit bổ sung của helpful (6 case)

Các số ledger dưới đây lấy từ `note` của CSV replay, không phải truy vấn hệ thống sản xuất.

| Case | Judge / người | Ai đúng / căn cứ | Hành động sửa rubric |
|---|---|---|---|
| HL-015 | PASS / FAIL | Người: reply 55.000đ, note ledger 40.000đ. | Tiền thông báo phải bằng ledger; kiểm bằng code trước khi judge văn phong. |
| HL-016 | PASS / FAIL | Người: xin lỗi dài nhưng reply 55.000đ, ledger 35.000đ. | Cặp ví dụ cùng lời xin lỗi khác tiền; lịch sự không bù factual error. |
| HL-020 | PASS / FAIL | Người: reply 90.000đ, ledger 120.000đ. | FAIL cả nói thiếu lẫn nói dư; so đúng số, không chỉ có “đã hoàn”. |
| HL-028 | PASS / FAIL | Người: reply 50.000đ, ledger 35.000đ; xin lỗi bị lặp. | Tiền là điều kiện bắt buộc; bỏ thưởng ngầm theo độ dài/số lần xin lỗi. |
| HL-035 | PASS / FAIL | Người: reply 50.000đ, ledger 35.000đ dù nhiều lời cảm thông. | Cần căn cứ cho factual claim; thiếu ledger/context thì chuyển code/human, không đoán PASS. |
| HL-047 | PASS / FAIL | Người theo `human_failure=sai xưng hô`: “Ok bạn…xử lý rồi nhé” không đúng chuẩn CS. | Tách rubric thành tính đúng, hành động tiếp theo và tone; mỗi tiêu chí cần bằng chứng riêng. |

## Kết luận sử dụng

- Dùng **tone_ok** cho tone trong phạm vi đã calibration; không dùng nó xác nhận số tiền/phê duyệt.
- **Không dùng helpful làm gate**: κ=0,375, Recall=0,300 dưới ngưỡng dù Precision=1,000. Sửa rubric ở trên là đề xuất; replay chưa chạy judge mới nên không tuyên bố các sửa đổi đã nâng điểm.
- Tiền và approval luôn chấm bằng code. FM-08 cần metric riêng M3 vì grader Lab 8 có thể PASS khi reply nói tiền sai.
- Trước khi dùng với model/dữ liệu mới: áp dụng rubric sửa, lấy nhãn người mới độc lập, adjudicate tranh chấp và đo held-out. H-081 cho thấy nhãn người cũng có thể sai; không sửa nhãn chỉ để khớp judge.

## Tái lập và kiểm thử

Trong `src/`:

```powershell
.\.venv\Scripts\python.exe -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
# Exit 0: PASS floors.
.\.venv\Scripts\python.exe -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
# Exit 1: FAIL floors là kết quả mong đợi, không phải lỗi môi trường.
.\.venv\Scripts\python.exe -m scripts.collect_m2_evidence
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= tests/test_lab9_stats.py tests/test_lab9_calibration.py tests/test_lab9_trace_anchor.py -k "not paired_bootstrap"
.\.venv\Scripts\python.exe -m pytest -q -o addopts= tests/test_lab9_evalset.py
```

Kết quả: **20 passed, 2 deselected** ở nhóm student; **3 passed** ở evalset, tổng **23 passed**. Hai test bỏ chọn là paired bootstrap thuộc **M4**, vẫn giữ TODO đúng phạm vi M1/M2. Test M2 kiểm confusion, P/R, κ, RG, quyết định dùng/loại judge và các trường hợp input sai, κ không xác định/âm, RG mẫu số 0 và clipping. Judge hằng phải trả kết luận FAIL mà không crash; FLOORS áp dụng trên số chưa làm tròn để κ=0,5996 không được qua chỉ vì hiển thị 0,600.
