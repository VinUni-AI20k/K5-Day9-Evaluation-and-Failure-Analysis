# Judge audit — replay công khai

Từ src/, chạy python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
và cùng lệnh với judge_helpful_public.csv --audit 5.
Output nguyên bản được script lưu trong src/reports/verification.json.
FAIL là lớp dương: TP/FP/FN/TN đo việc tìm lỗi.

| Tiêu chí | n | TP | FP | FN | TN | κ | Precision | Recall | Kết luận |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| tone_ok | 100 | 24 | 4 | 6 | 66 | 0.757 | 0.857 | 0.800 | Đạt κ≥0.6, P≥0.8, R≥0.7; dùng cho tone trong phạm vi replay |
| helpful | 100 | 9 | 0 | 21 | 70 | 0.375 | 1.000 | 0.300 | Loại khỏi gate: bỏ sót 21/30 lỗi, κ dưới sàn |

Rogan–Gladen: tone quan sát tỷ lệ FAIL 0.28, hiệu chỉnh 0.30; helpful quan sát 0.09, hiệu chỉnh 0.30.
Hiệu chỉnh tỷ lệ không làm judge recall thấp trở thành judge đủ điều kiện.
Kappa không xác định phải FAIL calibration.

## Audit bất đồng và hành động sửa rubric

Các quyết định dựa trên reply và note công khai; chưa phải vòng gán nhãn người độc lập mới.
Không sửa CSV để làm đẹp calibration.

| Case | Judge / human | Ai đúng theo bằng chứng hiện có? | Hành động sửa rubric |
|---|---|---|---|
| H-008 | PASS / FAIL | Human: “em”, “nha”, “check giúp em” quá suồng sã theo note CS | Thêm ví dụ thân thiện nhưng suồng sã vẫn FAIL; dùng anh/chị nhất quán |
| H-017 | PASS / FAIL | Human theo note: xưng “bạn” không hợp ngữ cảnh khách | Cung cấp ngữ cảnh xưng hô; thiếu thì chuyển người, không tự suy tuổi từ reply |
| H-029 | PASS / FAIL | Human: “không cần nhắn thêm” mang tính ra lệnh | Chấm toàn câu, không cho PASS chỉ nhờ “Dạ, vui lòng” |
| H-042 | FAIL / PASS | Human: ngắn nhưng lịch sự, có tiền và thời gian nhận | Không bắt buộc xin lỗi mọi reply; thêm ví dụ PASS ngắn |
| H-051 | FAIL / PASS | Human theo note: thuật ngữ refund được CS cho phép | Whitelist thuật ngữ, không phạt trộn tiếng Anh máy móc |
| H-063 | PASS / FAIL | Human theo note: hứa hoàn thêm ngoài kết quả hệ thống | Kiểm chứng lời hứa riêng với tone; lời hứa thêm phải có bằng chứng |
| H-070 | PASS / FAIL | Human: emoji cười không phù hợp khiếu nại | Thêm negative example emoji trong ngữ cảnh bồi thường |
| H-081 | FAIL / PASS | Note nguồn đánh dấu nhãn người sai, judge đúng; thiếu ticket để xác minh độc lập | Đưa vào adjudication; giữ CSV hiện tại, chỉ sửa ở phiên bản dữ liệu mới sau duyệt |
| H-088 | FAIL / PASS | Human: lặp “Dạ” nhỏ không đủ đánh FAIL tone | Phân mức lỗi gõ nhẹ, không coi ngang giọng thô lỗ |
| H-094 | PASS / FAIL | Human theo quy định tiếng Việt có dấu của nguồn | Bổ sung tiêu chí chất lượng tiếng Việt và ví dụ thiếu dấu |
| HL-015 | PASS / FAIL | Human: reply=55.000đ nhưng note ledger=40.000đ | Dùng code so reply-ledger, không dùng lịch sự suy tính đúng |
| HL-016 | PASS / FAIL | Human: reply=55.000đ, note ledger=35.000đ dù xin lỗi dài | Tách verbosity/tone khỏi đúng nghiệp vụ; tiền sai phải FAIL |

## Quyết định và giới hạn

- Giữ tone judge cho diễn đạt đã calibration; không dùng nó quyết định tiền/approval.
- Loại helpful khỏi release gate. Precision=1 không bù recall=0.3; câu trôi chảy che lỗi tiền.
- ReplyAmountCorrect dùng ledger thực của Trial. Ledger trong CSV audit chỉ có note nguồn, không phải DB được truy xuất lại.
- Cần human-labelled held-out mới và adjudication độc lập sau sửa rubric.
- Replay không thay đổi nên chưa tuyên bố rubric đề xuất đã cải thiện judge.
