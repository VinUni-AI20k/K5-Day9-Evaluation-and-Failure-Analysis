# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

```text
$ python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
n=100 P=0.857 R=0.8 kappa=0.757 {'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}
fail rate observed 0.28 -> corrected 0.3
PASS floors {'kappa': 0.6, 'precision': 0.8, 'recall': 0.7}          # exit 0

$ python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 10
n=100 P=1.0 R=0.3 kappa=0.375 {'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}
fail rate observed 0.09 -> corrected 0.3
FAIL floors {'kappa': 0.6, 'precision': 0.8, 'recall': 0.7}          # exit 1
```
Lớp dương = `FAIL` (việc của judge là tìm lỗi). Judge chạy ở chế độ replay: kết quả lấy từ CSV, không gọi model.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (cả 3 ngưỡng) | **dùng**: tiêu chí phụ về giọng văn, không thay grader code về tiền/approval |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (κ < 0.6, R < 0.7) | **loại**: không dùng làm gate |

Ma trận nhầm lẫn (hàng = người, cột = judge):

| | judge FAIL | judge PASS |
|---|---|---|
| **tone_ok** người FAIL | tp = 24 | fn = 6 |
| **tone_ok** người PASS | fp = 4 | tn = 66 |
| **helpful** người FAIL | tp = 9 | **fn = 21** |
| **helpful** người PASS | fp = 0 | tn = 70 |

Hiệu chỉnh Rogan-Gladen (sens = recall, spec = tn/(tn+fp)):
- tone_ok: sens 0.80, spec 66/70 = 0.943 → tỉ lệ lỗi quan sát 0.28 → hiệu chỉnh **0.30**, khớp tỉ lệ người gán FAIL (30/100).
- helpful: sens 0.30, spec 70/70 = 1.000 → quan sát 0.09 → hiệu chỉnh **0.30**. Judge `helpful` thấy chưa tới 1/3 số lỗi thật.

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | tone H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã với khách khiếu nại; judge nhầm suồng sã là thân thiện. **Sửa rubric:** thêm quy tắc xưng hô bắt buộc "LogiX – anh/chị"; xưng "em/bạn" hoặc trợ từ "nha/nhé" ⇒ FAIL. |
| 2 | tone H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ…" | PASS | FAIL | Người | Cùng lỗi xưng "bạn". **Sửa rubric:** gom vào quy tắc xưng hô ở case 1, kèm ví dụ few-shot FAIL. |
| 3 | tone H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh, gạt khách đi; judge chỉ thấy từ lịch sự "Dạ, vui lòng". **Sửa rubric:** chấm theo ý cả câu, không theo từ khóa; câu cấm/ra lệnh khách ("không cần…", "đừng…") ⇒ FAIL. |
| 4 | tone H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt vì "thiếu xin lỗi". **Sửa rubric:** ghi rõ "xin lỗi là không bắt buộc"; không phạt câu ngắn, lịch sự. |
| 5 | tone H-051 "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | Người | Style guide CS LogiX cho phép từ "refund". **Sửa rubric:** thêm danh sách từ tiếng Anh được phép (refund, ship, order). |
| 6 | tone H-063 "…đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người | Hứa "sẽ hoàn thêm" ngoài kết quả hệ thống: đây là **lỗi nội dung/cam kết**, không chỉ là giọng văn. **Sửa:** tách khỏi tone; thêm vào rubric "không hứa hành động ngoài kết quả hệ thống" và kiểm bằng code (reply chỉ nêu số trong ledger, liên quan FM-08). |
| 7 | tone H-070 "…cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Emoji cười trong ngữ cảnh khiếu nại. **Sửa rubric:** cấm emoji trong reply khiếu nại/hoàn tiền; có thể kiểm thêm bằng regex. |
| 8 | tone H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** | Nhãn người sai (người gán nhãn đọc nhầm ticket). **Hành động:** sửa nhãn trong bộ nhãn người ở lần gán nhãn sau và ghi nguồn sai; không sửa rubric. Sửa nhãn này chuyển 1 fp thành tp (tp 25, fp 3): P = 25/28 = 0.893, R = 25/31 = 0.806. |
| 9 | tone H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ…" | FAIL | PASS | Người (lỗi nhỏ) | Lặp "Dạ" do gõ nhầm, không phải giọng thô lỗ. **Sửa rubric:** lỗi chính tả/lặp từ nhẹ không tính là FAIL tone (tách thành tiêu chí "chính tả" riêng nếu cần). |
| 10 | tone H-094 "Da, LogiX da hoan 40.000đ…, xin loi vi su bat tien." | PASS | FAIL | Người | Mất dấu tiếng Việt (dịch máy), khách khó đọc. **Sửa rubric:** reply tiếng Việt không dấu ⇒ FAIL. |
| 11 | helpful HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." (ledger 40.000đ) | PASS | FAIL | Người | Sai tiền. Judge không thấy ledger nên không thể biết số tiền sai. **Hành động:** tiền luôn chấm bằng code (metric FM-08 so reply với `snapshot.refund_vnd`), không đưa vào rubric judge. |
| 12 | helpful HL-016 (xin lỗi 2 lần, "đã hoàn 55.000đ", ledger 35.000đ) | PASS | FAIL | Người | Judge bị lừa bởi câu xin lỗi dài, dài dòng (verbosity bias) và bỏ qua số tiền sai. **Hành động:** như case 11; rubric helpful thêm "lặp câu xin lỗi/đệm không thêm thông tin ⇒ không tính là hữu ích". |
| 13 | helpful HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | Người | Sai xưng hô và không nêu kết quả cụ thể (số tiền, trạng thái). **Sửa rubric:** reply hữu ích phải nêu trạng thái + số tiền (nếu có); lỗi xưng hô chuyển sang tiêu chí tone. |

## Kết luận
- **tone_ok: dùng được.** κ = 0.757, P = 0.857, R = 0.80, đạt cả 3 ngưỡng. Lỗi còn lại phần lớn do rubric mơ hồ về xưng hô, ra lệnh, emoji và không dấu (6/10 bất đồng là judge bỏ sót, tức fn), cộng 1 nhãn người sai (H-081). Chỉ dùng làm metric về giọng văn; không được dùng để chấm tiền hay approval.
- **helpful: bị loại, không dùng làm gate.** Ma trận nhầm lẫn tp 9 / fp 0 / **fn 21** / tn 70 cho thấy:
  - **Recall 0.30 < 0.7:** judge bỏ sót 21/30 reply người đánh FAIL. Gate dựa vào nó sẽ cho qua khoảng 70% reply tệ.
  - **κ 0.375 < 0.6:** mức đồng thuận vượt ngẫu nhiên thấp.
  - **Precision 1.0 không cứu được:** judge gần như luôn nói PASS (91/100), nên P cao chỉ vì hiếm khi nói FAIL.
  - **Nguyên nhân chính:** 18/21 lỗi bị bỏ sót là "sai tiền" (reply nói số khác ledger). Judge chỉ đọc văn bản, không có ledger, nên về cấu trúc không thể chấm đúng. Ngoài ra nó còn thiên vị reply dài và nhiều lời xin lỗi.
  - **Thay thế:** bắt lỗi sai tiền bằng grader code cho FM-08 (M3). 3 lỗi "sai xưng hô" thuộc tiêu chí tone_ok.
- **Hành động tiếp theo:**
  1. Cập nhật rubric tone theo các case 1–10 (xưng hô, ra lệnh, emoji, không dấu, từ tiếng Anh được phép, xin lỗi không bắt buộc).
  2. Sửa nhãn H-081.
  3. Gán nhãn người cho một tập mới rồi calibrate lại trước khi dùng rubric mới.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật. Hai CSV đều là n = 100 do một nhóm gán nhãn. Rubric sửa theo chính các case này có nguy cơ overfit nếu kiểm lại trên cùng dữ liệu.
