# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | CÓ (κ=0.757≥0.6, P=0.857≥0.8, R=0.800≥0.7) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | KHÔNG (κ=0.375<0.6, R=0.300<0.7) | loại |

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa Rubric |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người đúng | Câu trả lời *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* dùng xưng hô cá nhân suồng sã ("em - anh", "nha", "check"), không đúng chuẩn phong cách LogiX. Rubric cần thêm quy định rõ: không xưng hô "anh/em/bạn" tùy tiện, phải xưng "LogiX" và gọi "quý khách/anh/chị". |
| 2 | H-017 | PASS | FAIL | Người đúng | Câu trả lời *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* chứa các từ cảm thán suồng sã ("bạn ơi", "rồi nha"). Judge chỉ quét từ ngữ thô tục nên bỏ sót văn phong thiếu chuyên nghiệp. Cần cập nhật negative examples vào rubric của judge. |
| 3 | H-029 | PASS | FAIL | Người đúng | Câu trả lời *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* có giọng điệu gắt gỏng, xua đuổi khách hàng ("không cần nhắn thêm"). Judge đánh giá bề mặt có từ "vui lòng" nên cho qua. Rubric cần phạt nặng thái độ thiếu tôn trọng hoặc xua đuổi khách. |
| 4 | H-042 | FAIL | PASS | Người đúng | Câu trả lời *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* ngắn gọn, đủ thông tin và lịch sự. Judge phạt nhầm vì cho rằng câu văn quá ngắn. Cần làm rõ trong rubric: trả lời ngắn gọn, đúng trọng tâm không bị coi là lỗi thái độ. |
| 5 | H-051 | FAIL | PASS | Người đúng | Câu trả lời *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* dùng từ "refund" mượn tiếng Anh phổ biến trong TMĐT. Judge bắt bẻ lỗi pha trộn ngôn ngữ. Rubric cần cho phép các thuật ngữ chuyên môn phổ biến như "refund", "tracking". |

## Kết luận

- **Tiêu chí bị loại:** `helpful` bị LOẠI hoàn toàn khỏi CI gate vì không đạt ngưỡng tin cậy tối thiểu.
  - Ma trận nhầm lẫn: `tp=9, fp=0, fn=21, tn=70`.
  - Mặc dù độ chính xác Precision = 1.0 (không báo nhầm khi gán FAIL), Recall cực kỳ thấp (chỉ 0.300 = 30%), bỏ sót tới 21/30 trường hợp câu trả lời vô dụng hoặc sai thông tin (False Negative). Hệ số Cohen's Kappa chỉ đạt 0.375, phản ánh mức độ đồng thuận rất yếu giữa judge và người gán nhãn. Sử dụng judge này làm gate sẽ khiến 70% lỗi hữu ích lọt qua cửa kiểm soát.
- **Tiêu chí giữ lại:** `tone_ok` đạt chuẩn (κ=0.757, P=0.857, R=0.800) nhưng chỉ nên dùng ở mức monitor/advisory, không dùng làm blocking gate đối với các quyết định di chuyển dòng tiền.
- **Rủi ro còn lại:** Judge mới chỉ được kiểm định trên tập CSV replay công khai gồm 100 câu. Để đưa vào production, cần thu thập bộ nhãn kiểm thử mới (held-out set) được gán nhãn độc lập bởi chuyên gia chất lượng dịch vụ (QA) của LogiX.
