# Trace case: từ trace tới quyết định sai đầu tiên

Học viên: Dương Thị Huyền · MSSV 2A202604077

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-008 --seed 11
python -m lab9.trace_case --shape fixed --claim C-008 --seed 11   # đối chứng
```

Output (MockLLM, chạy lại lần nào cũng ra như vậy):

```
== seeded_regression C-008@11  lab8 grader: PASS (ok)
   1 handoff            {"contract_version": "handoff.v1", ... "task": "check_applicable_policy"}
   2 investigator       {"lookup_order": {"visible": true, "order": {"order_id": "O-808", "status": "delivered_late", ...
   3 quote              {"amount_vnd": 35000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03"], ...}
   4 refund_history     {"refund_count": 0, "refunded_vnd": 0}
   5 reply              {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}
-- ledger vs label
  refund_vnd     ledger=20000    label=20000
  refund_count   ledger=1        label=1
  status         result=resolved label=resolved

== fixed C-008@11  lab8 grader: PASS (ok)
   3 quote              {"amount_vnd": 35000, ...}
   4 reply              {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808."}
  refund_vnd     ledger=20000    label=20000
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-008@11`. Dòng `E-008@11` trong `reports/eval_seeded_regression.json`, run ID `E-seeded_regression-20261118-3744` |
| Triệu chứng | Grader Lab 8 (`pass_rate`) **PASS**, `refund_amount_correct` PASS (ledger 20.000 = nhãn), nhưng `reply_matches_ledger` FAIL. Reply báo khách "đã hoàn **35.000đ**" trong khi ledger chỉ ghi **20.000đ**, vì approval A-008 chặn trần ở 20.000 |
| Bước sai đầu tiên | Event **5** `reply`: `"Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."` |
| Vì sao là bước *đầu tiên* | Event 1–2: handoff và investigator đọc đúng đơn O-808 (giao trễ, đúng principal). Event 3: quote 35.000 đúng policy SHIP-LATE-03, khớp nhãn `proposal_amount` 35.000. Event 4: lịch sử hoàn bằng 0, nên không trừ gì (đúng). Sau đó host `issue_refund` cắt xuống 20.000 theo approval cap, ledger 20.000, cũng đúng. Chỉ đến reply ở event 5 agent mới báo số tự đề xuất thay cho số host đã ghi (`said = proposal` khi `pre_deducted`) |
| Failure mode | **FM-08** misreport (reply nói số tiền khác ledger). Đây là hệ quả của nhánh `pre_deducted` (FM-05) trong `seeded_regression`, nhưng ở claim này tiền trong ledger vẫn đúng, nên chỉ có FM-08 lộ ra |
| Đối chứng | `fixed C-008@11`: cùng quote 35.000, cùng ledger 20.000, nhưng event 4 `reply` nói "đã hoàn **20.000đ**", tức là báo đúng số host đã ghi |
| Regression test | `src/tests/test_lab9_trace_case.py`: `test_lab9_trace_case_c008_misreport_caught` (assert grader Lab 8 PASS nhưng `ReplyMatchesLedger` FAIL với reason chứa `35000`) và `test_lab9_trace_case_c008_fixed_passes` (fixed PASS). Cả hai đã chạy xanh, tức là grader fail trên variant lỗi và pass trên `fixed`. Ở cấp report, metric `reply_matches_ledger` (blocking) làm gate chặn `seeded_regression`: Δ −0.214, CI [−0.429, +0.000] trên v1, và `reply_matches_ledger` 0.7143 < 0.90 trên v2 |
| Chưa chắc chắn | Trace không cho biết reply có thực sự tới được khách không (MockLLM, không có kênh gửi). Grader dùng regex số tiền `\d{1,3}(.\d{3})+ đ`, nên reply viết số bằng chữ ("hai mươi nghìn") sẽ lọt. Với LLM thật cần thêm judge đã calibrate hoặc chuẩn hoá số |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai. Ở case này thì ngược lại: ledger đúng mà reply sai, nên grader chỉ đọc ledger cũng bỏ sót.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được (ở đây là `tests/test_lab9_trace_case.py`).
