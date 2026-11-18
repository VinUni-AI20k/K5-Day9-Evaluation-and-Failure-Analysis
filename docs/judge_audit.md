# Judge audit

Chạy (từ `src/`):
```
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 7
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 7
```
Lớp dương = `FAIL` (việc của judge là tìm lỗi). Floors: κ ≥ 0.6, P ≥ 0.8, R ≥ 0.7; κ không xác định ⇒ FAIL.

| Tiêu chí | n | κ | Precision | Recall | Confusion (tp/fp/fn/tn) | Tỉ lệ FAIL quan sát → hiệu chỉnh (Rogan-Gladen) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 24 / 4 / 6 / 66 | 0.28 → 0.30 | ✅ PASS | **dùng** (chỉ cho tone, không cho tiền) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | 9 / 0 / 21 / 70 | 0.09 → 0.30 | ❌ FAIL (κ, R dưới sàn) | **loại** |

Output gốc:
```
tone_ok : n=100 P=0.857 R=0.8 kappa=0.757 {'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}
          fail rate observed 0.28 -> corrected 0.3          PASS floors
helpful : n=100 P=1.0 R=0.3 kappa=0.375 {'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}
          fail rate observed 0.09 -> corrected 0.3          FAIL floors
```

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | tone H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em", dùng "nha" với khách là quá suồng sã cho kênh khiếu nại. Rubric: bắt buộc xưng "LogiX" / "anh/chị"; "em/bạn/nha" → FAIL tone. |
| 2 | tone H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha." | PASS | FAIL | Người | Judge thấy "Dạ" nên cho là lịch sự. Rubric: một từ kính ngữ ở đầu câu không bù được cách xưng hô sai ("bạn ơi", "nha") → FAIL. |
| 3 | tone H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người | Judge chấm theo từ khóa "Dạ, vui lòng". Rubric: chấm giọng của cả câu; câu mệnh lệnh hoặc gạt khách ("không cần nhắn thêm") → FAIL. |
| 4 | tone H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Judge phạt vì "thiếu xin lỗi". Rubric: xin lỗi **không bắt buộc**; reply ngắn, lịch sự, đủ ý → PASS. |
| 5 | tone H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | Judge phạt từ tiếng Anh. Rubric: thêm whitelist thuật ngữ được style guide CS cho phép (`refund`, `ship`, `voucher`). |
| 6 | tone H-063 "Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người | Giọng thì ổn nhưng hứa hẹn ngoài kết quả hệ thống. Đây là lỗi **nội dung**, không phải tone: chuyển cho grader code (reply vs ledger, FM-08), không dồn vào judge tone. |
| 7 | tone H-070 "Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Rubric: emoji cười trong ngữ cảnh khiếu nại → FAIL tone. |
| 8 | helpful HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." (ledger 40.000đ) | PASS | FAIL | Người | Judge không thấy ledger nên reply trôi chảy là được PASS. **Không chấm số tiền bằng judge**; dùng grader code `reply_amount_matches_ledger` (M3). |
| 9 | helpful HL-020 "Dạ, LogiX đã hoàn 90.000đ cho đơn O-303 ạ." (ledger 120.000đ) | PASS | FAIL | Người | Lỗi giống #8: sai tiền nhưng đúng giọng. Một judge chỉ đọc text không bao giờ bắt được loại lỗi này. |
| 10 | helpful HL-016 / HL-028 / HL-035 "Dạ, LogiX thành thật xin lỗi… mong anh/chị thông cảm…" (ledger 35.000đ) | PASS | FAIL | Người | Reply toàn xin lỗi, không có số tiền, mã đơn hay bước tiếp theo. Rubric: reply **không nêu số tiền đã hoàn và mã đơn** → FAIL helpful, dù lời lẽ lịch sự. |

Tổng kết bất đồng: tone có 10 (6 FN, 4 FP); helpful có 21, **toàn bộ là FN** (judge nói PASS, người nói FAIL).

## Kết luận

- **`tone_ok`: dùng được** làm judge, nhưng chỉ cho giọng văn. κ = 0.757, P = 0.857, R = 0.80 đều đạt floors. 6 FN tập trung ở xưng hô suồng sã, giọng ra lệnh và emoji; 4 FP ở chỗ đòi xin lỗi và cấm từ tiếng Anh. Sửa rubric theo các case #1–#7 rồi calibrate lại trên nhãn mới.
- **`helpful`: loại, không được làm gate.**
  - Recall = 0.30: judge chỉ bắt 9/30 reply lỗi, **bỏ sót 21 (70%)**. κ = 0.375 < 0.6.
  - Precision = 1.0 dễ gây hiểu lầm: judge "không báo nhầm" chỉ vì nó gần như không bao giờ nói FAIL.
  - Tỉ lệ FAIL quan sát 9% sau hiệu chỉnh Rogan-Gladen là khoảng **30%**, tức judge che mất khoảng 2/3 số reply lỗi. Nếu dùng làm gate, gate sẽ cho qua phần lớn regression.
  - Phần lớn FN là reply nói **số tiền khác ledger** (#8, #9). Theo quy tắc của lab, tiền và approval luôn chấm bằng **code** (`refund_amount_correct`, `reply_amount_matches_ledger`), không bằng judge. Số còn lại là reply rỗng nội dung (#10), sửa được bằng rubric "phải nêu số tiền + mã đơn".
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu **replay CSV công khai** (100 dòng mỗi tiêu chí, nhãn người đã biết trước). Chưa có tập held-out, chưa kiểm judge trên reply của agent thật hay LLM thật. Cần nhãn người mới để có held-out thật trước khi tin judge tone ở mức production; với n = 100 thì khoảng tin cậy của κ, P, R vẫn còn rộng.
