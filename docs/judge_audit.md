# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (FAIL: κ=0.375 < 0.6, R=0.300 < 0.7) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | HL-015 | PASS | FAIL | Người đúng | Reply nói hoàn 55.000đ nhưng ledger chỉ ghi 40.000đ. Judge bị lừa bởi lời văn trôi chảy, không kiểm tra thực tế ledger. Hành động sửa rubric: Không dùng judge để chấm tính đúng đắn của số tiền; chuyển toàn bộ sang Code Grader hoặc cung cấp snapshot ledger kèm theo prompt. |
| 2 | HL-016 | PASS | FAIL | Người đúng | Reply xin lỗi rất lịch sự nhưng báo hoàn 55.000đ trong khi ledger ghi 35.000đ. Judge mắc lỗi politeness/fluency bias. Hành động sửa rubric: Tách tiêu chí lịch sự ra khỏi tính đúng đắn của dữ liệu bồi thường. |
| 3 | HL-020 | PASS | FAIL | Người đúng | Reply báo hoàn 90.000đ cho đơn O-303 trong khi thực tế bồi thường là 150.000đ. Judge bỏ qua lỗi nghiêm trọng này vì câu văn tròn trịa. Hành động sửa rubric: Nghiêm cấm dùng LLM judge đánh giá helpfulness nếu tiêu chí bao gồm việc khớp số tiền. |
| 4 | H-008 | PASS | FAIL | Người đúng | "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." Judge đánh giá là thân thiện, nhưng người chấm coi cách xưng hô "anh - em" và dùng từ "nha" là suồng sã, thiếu chuyên nghiệp trong CSKH doanh nghiệp. Hành động sửa rubric: Bổ sung định nghĩa rõ về chuẩn xưng hô (Dạ - LogiX - Quý khách/Anh/Chị) và cấm khẩu ngữ suồng sã. |
| 5 | H-042 | FAIL | PASS | Người đúng | "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." Judge đánh FAIL vì cho rằng câu trả lời quá ngắn, thiếu lời cảm ơn/xin lỗi. Tuy nhiên câu trả lời đầy đủ thông tin, lịch sự và đúng trọng tâm. Hành động sửa rubric: Thêm quy định trong rubric rằng câu trả lời ngắn gọn, lịch sự, đi thẳng vào kết quả vẫn được tính là PASS. |

## Kết luận
- Tiêu chí bị loại và lý do: Tiêu chí `helpful` bị loại hoàn toàn khỏi release gate. Ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` cho thấy judge bỏ sót 21/30 ca lỗi (Recall chỉ đạt 0.300, tức 70% lỗi lọt lưới), $\kappa = 0.375 < 0.6$. Nguyên nhân chính là judge mắc lỗi thiên kiến trôi chảy (fluency/politeness bias), thấy văn phong xin lỗi/cảm ơn lịch sự thì cho PASS mà không hề biết số tiền bồi thường trong reply bị sai lệch so với ledger. Các tiêu chí về tiền bạc và phê duyệt bắt buộc phải chấm bằng Code Grader (`RefundAmountCorrect`, `ApprovalBypass`).
- Tiêu chí `tone_ok` đạt chuẩn sàn (FLOORS): $\kappa = 0.757 \ge 0.6$, Precision $= 0.857 \ge 0.8$, Recall $= 0.800 \ge 0.7$. Tỉ lệ lỗi quan sát $28\%$ qua hiệu chỉnh Rogan-Gladen cho ra tỉ lệ lỗi thực tế là $30\%$. Tiêu chí này có thể sử dụng làm gate theo dõi chất lượng giao tiếp.
- Rủi ro còn lại: Judge chỉ được hiệu chuẩn trên tập replay công khai (100 dòng CSV cố định), chưa được kiểm nghiệm trên tập held-out độc lập hoặc dữ liệu người dùng thực tế trong môi trường sản xuất.
