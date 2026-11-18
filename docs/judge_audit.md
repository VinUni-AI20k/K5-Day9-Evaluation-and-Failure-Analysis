# Judge Audit — LogiX-VN Refund Agent

## 1. Calibration method

Command:

```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

Both public calibration datasets contain 100 labeled examples. The evaluation compares Judge predictions against human reference labels using precision, recall and Cohen's kappa.

Acceptance floors:

- Cohen's κ ≥ 0.6
- Precision ≥ 0.8
- Recall ≥ 0.7

## 2. Calibration results

| Criterion | n | κ | Precision | Recall | Meets all floors? | Decision |
|---|---:|---:|---:|---:|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Yes | Use |
| helpful | 100 | 0.375 | 1.000 | 0.300 | No | Exclude from blocking |

### Confusion matrices

| Criterion | TP | FP | FN | TN |
|---|---:|---:|---:|---:|
| tone_ok | 24 | 4 | 6 | 66 |
| helpful | 9 | 0 | 21 | 70 |

### Interpretation

**tone_ok**

The Judge passes all three acceptance floors. Its agreement with human labels is sufficiently reliable for use as an evaluation signal, although disagreements still require human review.

**helpful**

The Judge fails the kappa and recall floors. Although precision is 1.0, recall is only 0.3: it misses 21 of the 30 human-labeled FAIL examples. Therefore, it must not be used as a blocking metric.

## 3. Manual disagreement audit

The following cases were returned by `--audit 5`.

| # | Case | Judge | Human | Correct reference | Observation |
|---:|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Human | Claiming that the refund is completed does not by itself establish an appropriately handled response |
| 2 | H-017 | PASS | FAIL | Human | A polite confirmation of a refund can still fail the tone rubric |
| 3 | H-029 | PASS | FAIL | Human | Asking the customer not to send more messages may be inappropriate despite polite wording |
| 4 | H-042 | FAIL | PASS | Human | The response gives a refund amount and an expected 3–5 day settlement period |
| 5 | H-051 | FAIL | PASS | Human | The response communicates a refund confirmation in concise, polite language |
| 6 | HL-015 | PASS | FAIL | Human | Refund confirmation alone does not demonstrate helpfulness |
| 7 | HL-016 | PASS | FAIL | Human | An apology without a concrete next step is insufficiently helpful |
| 8 | HL-020 | PASS | FAIL | Human | Refund confirmation alone does not demonstrate helpfulness |
| 9 | HL-028 | PASS | FAIL | Human | An apology without a concrete next step is insufficiently helpful |
| 10 | HL-035 | PASS | FAIL | Human | An apology without actionable guidance is insufficiently helpful |

## 4. Rubric improvement actions

### tone_ok

1. Evaluate whether the response is respectful and appropriate in context, not merely whether it contains polite phrases.
2. Treat instructions that dismiss or unnecessarily silence the customer as potential tone failures.
3. Distinguish concise but respectful refund confirmations from dismissive or misleading confirmations.
4. Add contrastive examples covering polite wording with inappropriate intent and concise wording that remains respectful.
5. Retain human review for borderline cases.

### helpful

1. Require a concrete next step, relevant status or actionable guidance where the customer's issue is unresolved.
2. Do not treat apologies or refund confirmations alone as sufficient evidence of helpfulness.
3. Add negative examples where polite language lacks useful information.
4. Recalibrate the Judge using a separate held-out human-labeled dataset before reconsidering it as a blocking signal.

## 5. Final decision

- **tone_ok: USE.** The Judge meets κ, precision and recall floors.
- **helpful: EXCLUDE FROM BLOCKING.** Its κ and recall are below the acceptance floors, and it misses 70% of human-labeled FAIL examples.

The helpfulness Judge may be retained for experimentation, but its output must not independently determine whether a PR passes the evaluation gate.

## 6. Remaining risks

The calibration datasets are public replay data. They do not establish generalization to unseen customer conversations or new human annotators.

A genuinely held-out dataset with independent human labels is required before claiming production-level judge reliability. Calibration should be repeated when the rubric, Judge prompt or evaluation population changes.

The audit examples are evidence of disagreement patterns, not proof that all similar responses should receive the same label without context.
