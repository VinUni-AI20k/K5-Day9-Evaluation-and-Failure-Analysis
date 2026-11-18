# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7) | **dùng** |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (κ=0.375 < 0.6, R=0.300 < 0.7) | **loại** |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (tone) | PASS | FAIL | Người đúng | Reply: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* Judge nhầm lẫn giữa thân thiện và thiếu chuyên nghiệp. **Sửa rubric:** Cấm đại từ xưng hô suồng sã ("em/anh"), cấm đuôi từ suồng sã ("nha", "nhé"), cấm chêm từ lóng ("check"). Quy chuẩn hóa xưng hô: "Dạ, LogiX xin thông báo...". |
| 2 | `H-042` (tone) | FAIL | PASS | Người đúng | Reply: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* Judge phạt quá khắt khe vì cho rằng thiếu lời xin lỗi. **Sửa rubric:** Với thông báo hoàn tiền thành công, lời xin lỗi là tùy chọn (optional), không phạt khi phản hồi đã đủ ý, lịch sự, rõ ràng. |
| 3 | `H-051` (tone) | FAIL | PASS | Người đúng | Reply: *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* Judge phạt vì dùng từ tiếng Anh ("refund"). **Sửa rubric:** Bổ sung danh sách whitelist thuật ngữ TMĐT/CSKH phổ biến được chấp nhận như "refund", "order", "voucher". |
| 4 | `HL-015` (helpful) | PASS | FAIL | Người đúng | Reply: *"Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ."* nhưng ledger chỉ ghi 40.000đ (sai tiền). Judge bị đánh lừa bởi văn phong lịch sự, không kiểm tra được số tiền thực tế. **Hành động:** Loại judge này; việc kiểm tra số tiền hoàn và trạng thái phải giao cho code grader (`RefundAmountCorrect`), không dùng LLM judge. |
| 5 | `HL-016` (helpful) | PASS | FAIL | Người đúng | Reply: *"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này..."* (xin lỗi suông, không giải quyết vấn đề, bỏ qua việc hoàn tiền 35.000đ đã ghi nhận). Judge đánh giá PASS vì văn phong quá lễ phép. **Sửa rubric:** Phản hồi chỉ được xem là helpful khi nêu rõ kết quả xử lý và hướng giải quyết cụ thể, văn phong xin lỗi suông không đủ điều kiện PASS. |

## Kết luận
- **Tiêu chí bị loại:** `judge_helpful` bị **loại bỏ hoàn toàn**, không được dùng làm gate chặn PR.
  - *Dẫn chứng ma trận nhầm lẫn:* `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` trên 100 mẫu.
  - *Nguyên nhân:* Tỉ lệ bỏ lọt lỗi cực kỳ nghiêm trọng (`fn = 21` trên tổng số 30 ca lỗi người gán nhãn), dẫn đến Recall sụt giảm chỉ còn `0.30` (thấp hơn nhiều so với sàn `0.70`), Cohen's Kappa chỉ đạt `0.375` (dưới sàn `0.60`). Tỉ lệ lỗi quan sát qua judge chỉ là 9% trong khi tỉ lệ lỗi thực tế lên tới 30% (Rogan-Gladen corrected rate = 0.30). Judge bị "hào quang" của văn phong lịch sự, trôi chảy che lấp các lỗi sai tiền và thiếu sót thông tin thực tế.
- **Tiêu chí được chọn:** `judge_tone` đạt toàn bộ các sàn kiểm định (κ=0.757, P=0.857, R=0.800) với ma trận `{'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}`, có thể dùng hỗ trợ đánh giá phong cách giao tiếp.
- **Rủi ro còn lại:** Cả hai judge hiện chỉ được hiệu chuẩn trên tập dữ liệu replay đã công khai (`judge_tone_public.csv`, `judge_helpful_public.csv`). Trong môi trường thực tế, nếu phân phối dữ liệu hội thoại của khách hàng thay đổi hoặc xuất hiện các tình huống giao tiếp mới (out-of-distribution), judge có thể bị suy giảm chất lượng. Do đó, cần định kỳ thu thập mẫu và gán nhãn thủ công (human labels) trên tập held-out mới để liên tục hiệu chuẩn lại judge.
