# Eval Card — LogiX-VN Refund Agent

## 1. Evaluation overview

**Mục tiêu:** Đánh giá độ an toàn, tính chính xác và độ ổn định của LogiX-VN Refund Agent trước khi triển khai thay đổi lên main.

| Thành phần | Cấu hình |
|---|---|
| Evaluation framework | Lab 9 — Evaluation and Failure Analysis |
| LLM | MockLLM |
| Eval set v1 | 14 items × 5 seeds = 70 trials |
| Eval set v1 SHA | `aed47217b15c` |
| Metric spec v1 | `1.0` |
| Eval set v2 | 28 items × 5 seeds = 140 trials |
| Eval set v2 SHA | `57cbb8385f2e` |
| Metric spec v2 | `2.0` |
| Seeds v1/v2 | `11, 22, 33, 44, 55` |

## 2. Version 1 — Core evaluation

### Baseline results

**Run ID:** `E-swarm-20261118-aed4`

| Metric | Baseline |
|---|---:|
| approval_bypass | 0 |
| secret_leak | 0 |
| db_fact_kept | 0.9857 |
| refund_amount_correct | 0.9857 |
| proposal_amount_correct | 0.9857 |
| reply_ledger_match | 0.0000 |
| pass_rate | 0.9857 |
| pass_5 | 0.9286 |
| cost_per_success | 49.5670 |

### Fixed variant

**Run ID:** `E-fixed-20261118-aed4`

| Metric | Fixed |
|---|---:|
| approval_bypass | 0 |
| secret_leak | 0 |
| db_fact_kept | 1.0000 |
| refund_amount_correct | 1.0000 |
| proposal_amount_correct | 1.0000 |
| reply_ledger_match | 0.0000 |
| pass_rate | 1.0000 |
| pass_5 | 1.0000 |
| cost_per_success | 48.7157 |

**Gate result:** PASS — exit 0 (merge).

Paired comparison against baseline:

- `refund_amount_correct`: Δ +0.014; 95% CI [+0.000, +0.043].
- `pass_rate`: Δ +0.014; 95% CI [+0.000, +0.043].

The fixed variant meets all configured v1 thresholds and does not introduce a detected safety violation.

### Seeded regression variant

**Run ID:** `E-seeded_regression-20261118-aed4`

| Metric | Seeded regression |
|---|---:|
| approval_bypass | 0 |
| secret_leak | 0 |
| db_fact_kept | 0.9286 |
| refund_amount_correct | 0.8571 |
| proposal_amount_correct | 0.7857 |
| reply_ledger_match | 0.2143 |
| pass_rate | 0.7143 |
| pass_5 | 0.7143 |
| cost_per_success | 81.2020 |

The regression variant shows degradation in database fact retention, refund amount correctness, proposal amount correctness and overall pass rate.

**Gate result: BLOCK — exit 1.**

The gate was run against the regenerated v1 baseline with the same eval-set SHA (`aed47217b15c`).

Blocking metrics:
- `refund_amount_correct = 0.8571` (minimum 0.95).
- `proposal_amount_correct = 0.7857` (minimum 0.95).
- `reply_ledger_match = 0.2143` (maximum 0).
- `pass_rate = 0.7143` (minimum 0.85).

The gate correctly blocks the regression. `db_fact_kept`, `pass_5`, and `cost_per_success` produce warnings but are not blocking metrics in this v1 specification.

## 3. Version 2 — Advanced evaluation

### Baseline

**Run ID:** `E-swarm-20261118-57cb`

| Metric | Baseline v2 |
|---|---:|
| approval_bypass | 0 |
| secret_leak | 0 |
| db_fact_kept | 0.9786 |
| refund_amount_correct | 0.9786 |
| reply_ledger_match | 0.0000 |
| pass_rate | 0.9786 |
| pass_5 | 0.8929 |
| pass_hat_5 | 0.8929 |
| cost_per_success | 50.8077 |

### Fixed and honest refactor

Both `fixed_v2.json` and `honest_v2.json` pass the v2 gate.

- Fixed: `pass_rate = 1.0000`, `pass_hat_5 = 1.0000`.
- Honest refactor: `pass_rate = 1.0000`, `pass_hat_5 = 1.0000`.

The honest refactor changes wording and execution path without changing the expected outcome. It should not be blocked solely because of implementation differences.

### Flaky regression

**Run ID:** `E-flaky_regression-20261118-57cb`

- `pass_rate = 0.9643`
- `pass_hat_5 = 0.8214`
- `reply_ledger_match = 0.0000`
- `refund_amount_correct = 0.9714`

The v2 gate blocks this variant because `pass_hat_5` falls below its blocking floor of 0.85 and the money-movement slice fails its configured paired comparison.

### Slice regression

**Run ID:** `E-slice_regression-20261118-57cb`

- `pass_rate = 0.9357`
- `pass_hat_5 = 0.8929`
- `refund_amount_correct = 0.9357`

This variant demonstrates why aggregate pass rate alone is insufficient: slice-level evaluation is needed to detect localized degradation.

## 4. Judge calibration

The judge calibration results are:

| Judge metric | Result |
|---|---:|
| Tone Cohen's κ | 0.757 |
| Tone precision | 0.857 |
| Tone recall | 0.800 |

**Conclusion:** The tone judge is usable as an evaluation signal, with remaining disagreement requiring human review.

The helpfulness judge is excluded from automated blocking because its calibration did not meet the required reliability. Disagreement cases and rubric improvements are documented in `docs/judge_audit.md`.

## 5. A/A reliability check

The A/A evaluation uses alternative seeds `66, 77, 88, 99, 110`.

Observed result: the A/A report has the same aggregate metrics as the v2 baseline, with Δ = 0 for the compared metrics.

This result demonstrates deterministic behavior under MockLLM for the tested configuration. It does not establish that a real LLM has zero sampling variance or that the benchmark captures all production sources of uncertainty.

## 6. Safety and failure analysis

The evaluation tracks safety failures separately from capability metrics. Safety violations must not be averaged away by improvements in other metrics.

Failure definitions, evidence and trace references are documented in `docs/failure_taxonomy.md`.

The first incorrect step and corresponding regression case are documented in `docs/trace_case.md`.

## 7. Limitations

- The evaluation uses MockLLM, not a production LLM or real customer traffic.
- V1 contains 14 evaluation items; v2 contains 28.
- Five seeds provide limited evidence for rare or intermittent failures.
- Judge calibration uses replayed judgments and does not fully represent human evaluation in production.
- Passing the benchmark does not guarantee the absence of unknown failure modes.
- The A/A result under MockLLM should not be generalized to stochastic production inference.

## 8. Gate policy and ownership

A PR must pass all blocking safety and capability metrics, including configured slice checks and integrity checks.

- `fixed` and `honest_refactor` should be allowed to merge.
- `seeded_regression`, `slice_regression` and `flaky_regression` should be blocked.
- Any integrity-check failure must block the evaluation rather than silently accepting an invalid report.

## 9. When to increase the eval-set version

Create a new eval-set version when:

1. A newly discovered failure mode is not represented by existing items.
2. New tools, workflows or business rules change the agent's behavior.
3. Production incidents reveal gaps in the current evaluation coverage.
4. New adversarial cases are added and require updated provenance and labels.

Do not loosen thresholds on the same eval-set version merely to make a failing PR pass. Threshold changes must be justified by calibration evidence and versioned evaluation policy.
