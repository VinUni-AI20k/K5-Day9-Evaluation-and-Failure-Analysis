# Judge audit

Học viên: Dương Thị Huyền · MSSV 2A202604077

Chạy: `python -m lab9.judge --csv <file> --audit 10` (backend REPLAY: verdict của judge đã lưu sẵn trong CSV, không gọi model). FAIL là lớp dương, vì việc của judge là **tìm lỗi**.

| Tiêu chí | n | κ | Precision | Recall | Specificity | Ma trận (tp/fp/fn/tn) | Tỉ lệ FAIL quan sát → hiệu chỉnh RG | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 0.943 | 24 / 4 / 6 / 66 | 0.28 → 0.30 | **PASS** | **dùng** (metric phụ, không chặn tiền) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | 1.000 | 9 / 0 / 21 / 70 | 0.09 → 0.30 | **FAIL** (κ, R) | **loại**: không được dùng làm gate |

Output gốc:
```
tone:    n=100 P=0.857 R=0.8 kappa=0.757 {'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}
         fail rate observed 0.28 -> corrected 0.3 · PASS floors
helpful: n=100 P=1.0 R=0.3 kappa=0.375 {'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}
         fail rate observed 0.09 -> corrected 0.3 · FAIL floors
```

## Audit thủ công 10 bất đồng của judge tone (cả 10 case `--audit`)

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" + "nha" là quá suồng sã với khách khiếu nại. **Rubric:** thêm luật cứng "xưng hô phải là LogiX / anh/chị; 'em', 'bạn', 'nha', 'nhé' = FAIL", kèm 2 ví dụ few-shot FAIL |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ … rồi nha." | PASS | FAIL | Người | Cùng lỗi xưng hô ("bạn ơi"). Luật ở #1 xử lý được |
| 3 | H-029 "Dạ, vui lòng chờ. … không cần nhắn thêm." | PASS | FAIL | Người | Judge chỉ nhìn kính ngữ "Dạ, vui lòng" mà bỏ qua giọng ra lệnh. **Rubric:** "kính ngữ ở đầu câu không cứu được câu mệnh lệnh / gạt khách ('không cần nhắn thêm')" |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Judge phạt vì "thiếu xin lỗi". **Rubric:** ghi rõ "xin lỗi không bắt buộc; ngắn, đủ ý, lịch sự = PASS" |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ …" | FAIL | PASS | Người | Style guide CS LogiX cho phép từ "refund". **Rubric:** thêm danh sách từ tiếng Anh được phép (refund, ship, voucher) |
| 6 | H-063 "… đã hoàn 20.000đ và sẽ hoàn thêm …" | PASS | FAIL | Người | Câu này hứa ngoài kết quả hệ thống. Đó là lỗi **nội dung** chứ không phải tone, nên tách khỏi rubric tone và để grader code bắt (FM-08 `reply_matches_ledger` + luật "không hứa hoàn thêm"). Rubric tone ghi: "hứa hẹn ngoài kết quả = FAIL" |
| 7 | H-070 "… đã hoàn 90.000đ … ạ 😂😂" | PASS | FAIL | Người | Emoji cười trong ngữ cảnh khiếu nại. **Rubric:** "emoji cảm xúc (😂🤣😜) = FAIL" |
| 8 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn …" | FAIL | PASS | **Judge** (theo note trong CSV) | Người đọc nhầm ticket, nên nhãn người sai. **Hành động:** sửa nhãn trong bộ vàng ở version sau và cho người thứ hai rà lại (double annotation) các case bất đồng |
| 9 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ …" | FAIL | PASS | Người | Lặp "Dạ" là lỗi gõ, không bất lịch sự. **Rubric:** "lỗi gõ nhỏ không đổi giọng điệu = PASS" |
| 10 | H-094 "Da, LogiX da hoan 40.000đ cho don O-341 …" | PASS | FAIL | Người | Mất dấu tiếng Việt (dịch máy). **Rubric:** "thiếu dấu tiếng Việt = FAIL (không chuyên nghiệp)" |

Tổng kết tone: 9/10 bất đồng là judge sai, 1/10 là nhãn người sai (H-081). Lỗi của judge rơi vào hai nhóm: bỏ sót tín hiệu suồng sã hoặc mệnh lệnh (FN: H-008, 017, 029, 063, 070, 094) và phạt oan văn phong ngắn (FP: H-042, 051, 088). Sửa rubric theo các dòng trên rồi calibrate lại trên một tập **held-out mới**, không dùng lại 100 dòng này.

## Judge helpful: vì sao bị loại

Phân tích 30 case người gán FAIL theo cột `human_failure`:

| Loại lỗi (người) | Judge bắt (FAIL) | Judge bỏ sót (PASS) |
|---|---|---|
| sai tiền | 0 | **18** |
| sai xưng hô | 0 | 3 |
| giọng cụt | 4 | 0 |
| không hỏi lại mã đơn | 3 | 0 |
| trả lời lạc đề | 2 | 0 |

- Recall 0.30: judge bỏ sót 21/30 reply lỗi, trong đó **18/18 case sai tiền** (ví dụ HL-015 "đã hoàn 55.000đ" trong khi ledger ghi 40.000đ, và HL-016 là một reply rất dài, nhiều câu xin lỗi, nhưng sai tiền). Judge không thấy ledger, nên một câu trôi chảy và lịch sự luôn được PASS.
- Precision 1.0 không cứu được: một gate dùng judge này sẽ báo tỉ lệ lỗi 9% trong khi tỉ lệ thật (Rogan-Gladen) là 30%, tức là đánh giá thấp lỗi khoảng 3 lần. κ = 0.375 < 0.6.
- **Kết luận:** không dùng `helpful` làm gate. Phần "đúng tiền" chuyển sang grader code `ReplyMatchesLedger` (FM-08) và `RefundAmountCorrect`, vì tiền và phê duyệt luôn chấm bằng code. Nếu muốn giữ một judge "helpful" thì phải hẹp lại thành "trả lời đúng câu hỏi và hỏi lại thông tin còn thiếu", bỏ phần tiền, viết lại rubric và calibrate lại.

## Kết luận
- **Dùng:** `tone_ok` (κ 0.757, P 0.857, R 0.80), nhưng chỉ làm metric theo dõi chất lượng giọng văn, không chặn release tiền.
- **Loại:** `helpful` (κ 0.375, R 0.30 < 0.7). Nhìn ma trận nhầm lẫn: fn = 21 lớn hơn nhiều tp = 9, và lỗi tập trung ở loại "sai tiền" mà judge không có dữ liệu để thấy.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai (100 dòng mỗi tiêu chí), và rubric đã được chỉnh theo chính các bất đồng này. Cần nhãn người mới để có held-out thật, và cần đo lại khi đổi model judge hay prompt.
