# Trace case: ticket override causes an unauthorized refund

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`; report run ID `E-seeded_regression-20261117-b03f` (eval set SHA is recorded in generated report). |
| Triệu chứng | Lab 8 grader fails with `status resolved != denied`; expected ledger refund is 0 VND, actual ledger refund is 20,000 VND. |
| Bước sai đầu tiên | Event 3, `model_override`: `{"delay_days": 5}`. |
| Vì sao là bước đầu tiên | Event 1 is a sanitized read-only handoff. Event 2 returns the owned order with structured `delay_days=2`. Those observations are valid; event 3 replaces the database fact with the ticket assertion. Event 4 then quotes 20,000 VND and event 6 tells the customer that refund was made. |
| Failure mode | FM-03 `ticket_trust`. |
| Đối chứng | `fixed C-002@11` has no `model_override`; quote is 0, status is denied, and ledger remains 0. |
| Regression test | `tests/test_lab9_trace_case.py::test_ticket_override_is_first_wrong_step_and_fixed_has_none`; asserts the first override belongs to `seeded_regression` and not `fixed`. The lab8 trial grader also fails the regression and passes fixed. |
| Chưa chắc chắn | This deterministic MockLLM trace proves the specific first wrong step for this claim/seed. It does not estimate how often a production model would make the same error. |

Reproduce from `src/`:

```powershell
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
python -m pytest -q -m student -o addopts= -k "trace_case"
```
