# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok (`judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | **Có** (0.757 ≥ 0.6, 0.857 ≥ 0.8, 0.800 ≥ 0.7) | **dùng** (kèm hiệu chỉnh Rogan-Gladen: observed fail rate `0.280` → corrected `0.300`) |
| helpful (`judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | **Không** (κ = 0.375 < 0.6, R = 0.300 < 0.7) | **loại** (không được dùng làm gate) |

## ≥5 case audit thủ công (trên `judge_tone_public.csv` và `judge_helpful_public.csv`)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa Rubric / Nhãn |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* — xưng `"em"` + tiểu từ `"nha"` quá suồng sã; judge nhầm là thân thiện. **Sửa rubric:** Bắt buộc xưng hô chuẩn `"LogiX"` – `"anh/chị"`, đánh `FAIL` nếu dùng `"em"`, `"bạn"`, `"nha"`, `"nhé"`. |
| 2 | `H-017` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* — xưng `"bạn ơi ... nha"` không chuẩn mực CSKH. **Sửa rubric:** Đưa danh sách từ cấm suồng sã (`"bạn ơi"`, `"rồi nha"`) vào prompt của judge. |
| 3 | `H-029` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* — vế sau mang giọng ra lệnh/cấm đoán khách; judge bị đánh lừa bởi cụm `"Dạ, vui lòng"` ở đầu câu. **Sửa rubric:** Yêu cầu judge xét toàn bộ các mệnh đề trong câu, đánh `FAIL` nếu có фразе chặn lời khách (`"không cần nhắn thêm"`, `"khỏi hỏi"`). |
| 4 | `H-042` (`tone_ok`) | `FAIL` | `PASS` | **Người đúng** | Reply: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* — câu ngắn gọn nhưng đầy đủ thông tin và lịch sự (`"Dạ ... ạ"`); judge phạt oan vì thiếu câu xin lỗi. **Sửa rubric:** Khi hoàn tiền thành công (`resolved`), không bắt buộc phải có lời xin lỗi dài dòng miễn có kính ngữ `"Dạ ... ạ"`. |
| 5 | `H-051` (`tone_ok`) | `FAIL` | `PASS` | **Người đúng** | Reply: *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* — quy chuẩn CSKH LogiX cho phép dùng từ `"refund"`; judge phạt oan vì pha tiếng Anh. **Sửa rubric:** Thêm ngoại lệ cho phép thuật ngữ nghiệp vụ `"refund"` / `"claim"`. |
| 6 | `H-063` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."* — tự ý hứa `"sẽ hoàn thêm"` ngoài quyết định hệ thống. **Sửa rubric:** Đánh `FAIL` mọi câu hứa hẹn bồi thường thêm không có trong kết quả xử lý. |
| 7 | `H-070` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"* — dùng emoji cợt nhả trong bối cảnh khiếu nại. **Sửa rubric:** Cấm sử dụng emoji cảm xúc đùa cợt (`😂`, `🤣`) trong phản hồi CSKH. |
| 8 | `H-081` (`tone_ok`) | `FAIL` | `PASS` | **Judge đúng** | Reply: *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* — câu thiếu câu kết hỗ trợ và người gán nhãn đọc nhầm ticket. **Hành động:** Sửa lại nhãn chuẩn của người (`human` → `FAIL`) trong bộ dữ liệu golden. |
| 9 | `H-088` (`tone_ok`) | `FAIL` | `PASS` | **Người đúng** | Reply: *"Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ."* — lỗi lặp từ nhẹ `"Dạ, dạ"` nhưng thái độ vẫn lịch sự. **Sửa rubric:** Không phạt `FAIL` về thái độ đối với lỗi lặp từ kính ngữ nhẹ. |
| 10 | `H-094` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien."* — mất toàn bộ dấu tiếng Việt. **Sửa rubric:** Bắt buộc phản hồi tiếng Việt phải có dấu chuẩn. |
| 11 | `HL-016`, `HL-028` (`helpful`) | `PASS` | `FAIL` | **Người đúng** | Reply lặp lại câu xin lỗi rất dài và lịch sự nhưng **báo sai số tiền hoàn so với ledger** (`55.000đ` vs `35.000đ`; `50.000đ` vs `35.000đ` — `FM-08`). Judge bị **verbosity/sycophancy bias** và không đọc được ledger nên cho `PASS`. **Hành động:** Loại bỏ judge `helpful` khỏi gate; chuyển việc kiểm tra số tiền trong `reply` so với `ledger` sang **Code Grader** (`M3`). |

## Kết luận
- **Tiêu chí được duyệt:** `tone_ok` đạt cả 3 ngưỡng sàn ($\kappa = 0.757 \ge 0.6$, $P = 0.857 \ge 0.8$, $R = 0.800 \ge 0.7$, ma trận nhầm lẫn `{'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}`). Tỉ lệ lỗi quan sát được là `0.280`, sau khi hiệu chỉnh sai số phân loại bằng **Rogan-Gladen** (với $\text{sens} = 0.800, \text{spec} = 66/70 \approx 0.943$) cho ra tỉ lệ lỗi thực ước lượng là **`0.300`** (khớp đúng $30/100$ lỗi thật của nhãn người).
- **Tiêu chí bị loại và lý do:** `helpful` bị **LOẠI** (không bao giờ được dùng làm CI gate) vì ma trận nhầm lẫn là `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`, dẫn tới **$\text{Recall} = 0.300 < 0.70$** và **$\kappa = 0.375 < 0.60$**. Nguyên nhân cốt lõi: Judge `helpful` bỏ lọt tới **21/30 ca lỗi (`fn = 21`)**, trong đó có **18 ca báo sai số tiền so với sổ cái (`sai tiền` / FM-08)** nhưng viết lời xin lỗi dài dòng làm judge bị thiên kiến lịch sự/dài dòng (verbosity & politeness bias). Theo nguyên tắc của dự án: **tiền và sự thật trong DB/ledger bắt buộc phải chấm bằng Code Grader, không dùng Judge**.
- **Rủi ro còn lại:** Judge `tone_ok` hiện chỉ được kiểm chuẩn trên tập dữ liệu replay đã công khai (`judge_tone_public.csv`, $n = 100$); nếu tinh chỉnh rubric dựa trên chính 10 ca bất đồng này thì điểm $\kappa$ trên tập cũ sẽ bị overfit. Do đó cần thu thập và gán nhãn người mới trên một tập **held-out độc lập** trước khi đưa rubric mới vào vận hành thực tế.

