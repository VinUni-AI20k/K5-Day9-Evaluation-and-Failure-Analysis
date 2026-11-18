# Trace case — FM-03: ticket_trust

## 1. Case identification

| Field | Value |
|---|---|
| Failure mode | FM-03 — `ticket_trust` |
| Claim | `C-002` |
| Seed | `11` |
| Shape | `seeded_regression` |
| Run ID | `E-seeded_regression-20261118-aed4` |
| Eval set SHA | `aed47217b15c` |
| Grader | `DbFactKept` |
| Metric | `db_fact_kept` |

## 2. Observed failure

Command:

```cmd
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
```

The grader reports:

```text
lab8 grader: FAIL (status resolved != denied)
```

The trace shows the following sequence:

| Step | Event | Observation |
|---|---|---|
| 1 | `handoff` | Agent receives the allowed tools and task context |
| 2 | `investigator` | Database investigation returns the authoritative order information |
| 3 | `model_override` | `delay_days` is overridden to `5` |
| 4 | `quote` | Agent calculates a compensation amount of 20,000 VND |
| 5 | `refund_history` | No previous refund is recorded |
| 6 | `reply` | Agent tells the customer that 20,000 VND has been refunded |

The taxonomy records the authoritative database value as `delay_days=2`, while the override changes it to `5`. This is FM-03: the agent trusts a conflicting ticket/model-provided fact instead of the authoritative database record.

The resulting ledger differs from the expected label:

| Field | Ledger | Expected label |
|---|---:|---:|
| `refund_vnd` | 20,000 | 0 |
| `refund_count` | 1 | 0 |
| `status` | `resolved` | `denied` |

## 3. Fixed-shape contrast

Command:

```cmd
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
```

Observed result:

```text
lab8 grader: PASS (ok)
```

The fixed trace has no `model_override` event. The quote is:

```json
{
  "amount_vnd": 0,
  "reason": "no_entitlement",
  "clause_ids": [],
  "parts": {}
}
```

The ledger remains at zero refunds, and the result status is `denied`, matching the expected label.

This contrast supports the diagnosis that the override is the first observed incorrect event in the seeded-regression trace.

## 4. Grader and regression evidence

The existing unit test in `tests/test_lab9_graders.py` is:

```python
def test_override_event_breaks_db_fact(graders):
    assert graders.DbFactKept().evaluate(
        ctx(trial(events=[{"kind": "model_override", "payload": {}}]))
    ).value is False
```

Verification:

```text
python -m pytest -q -o addopts= tests/test_lab9_graders.py

8 passed
```

This verifies that `DbFactKept` flags a `model_override` event. The test is a hand-built grader unit test; it is not a dedicated integration regression test that executes `C-002@11` against both shapes.

## 5. Root cause and corrective action

**Root cause:** The seeded-regression agent accepts an overridden delay value rather than preserving the authoritative database value.

**Corrective action:** Treat the database investigation result as the source of truth. Do not allow ticket or model-provided values to overwrite authoritative order fields.

**Regression protection:** Keep the `DbFactKept` assertion for override events and retain `C-002@11` as a trace-level diagnostic case for future evaluations.

## 6. Limitations

- This trace demonstrates one reproducible FM-03 failure at `C-002@11`, seed 11.
- The fixed-shape comparison passes for the same claim and seed.
- The existing grader unit test validates detection of an override event, but does not independently execute the full claim-level scenario.
- The evaluation uses a MockLLM and a 14-item v1 evaluation set; results should not be interpreted as production performance.