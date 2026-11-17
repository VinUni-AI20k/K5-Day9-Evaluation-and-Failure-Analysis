"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import math
import numbers

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    _validate_labels(human, judge)
    human_labels = [str(label).strip().upper() for label in human]
    judge_labels = [str(label).strip().upper() for label in judge]
    tp = sum(h == POS and j == POS for h, j in zip(human_labels, judge_labels))
    fp = sum(h != POS and j == POS for h, j in zip(human_labels, judge_labels))
    fn = sum(h == POS and j != POS for h, j in zip(human_labels, judge_labels))
    tn = sum(h != POS and j != POS for h, j in zip(human_labels, judge_labels))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    precision_denominator = cm["tp"] + cm["fp"]
    recall_denominator = cm["tp"] + cm["fn"]
    precision = cm["tp"] / precision_denominator if precision_denominator else 0.0
    recall = cm["tp"] / recall_denominator if recall_denominator else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = len(human)
    observed = (cm["tp"] + cm["tn"]) / n
    human_positive = (cm["tp"] + cm["fn"]) / n
    judge_positive = (cm["tp"] + cm["fp"]) / n
    expected = human_positive * judge_positive + (1 - human_positive) * (1 - judge_positive)
    if math.isclose(expected, 1.0):
        raise ValueError("Cohen's kappa is undefined when expected agreement is 1")
    return (observed - expected) / (1 - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    rates = (observed_rate, sensitivity, specificity)
    if any(not math.isfinite(value) or value < 0 or value > 1 for value in rates):
        raise ValueError("observed rate, sensitivity, and specificity must be finite values in [0, 1]")
    denominator = sensitivity + specificity - 1
    if math.isclose(denominator, 0.0):
        raise ValueError("Rogan-Gladen estimate is undefined when sensitivity + specificity = 1")
    corrected = (observed_rate + specificity - 1) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b) or not a:
        raise ValueError("paired bootstrap requires non-empty samples of equal length")
    if n_resamples <= 0 or not 0 < confidence < 1:
        raise ValueError("n_resamples must be positive and confidence must be in (0, 1)")
    a_values = np.asarray(a, dtype=float)
    b_values = np.asarray(b, dtype=float)
    if not np.all(np.isfinite(a_values)) or not np.all(np.isfinite(b_values)):
        raise ValueError("paired bootstrap samples must be finite")
    if np.array_equal(a_values, b_values):
        return 0.0, 0.0, 0.0

    def mean_difference(left: np.ndarray, right: np.ndarray, axis: int) -> np.ndarray:
        return np.mean(left - right, axis=axis)

    result = bootstrap(
        (a_values, b_values),
        mean_difference,
        paired=True,
        vectorized=True,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="percentile",
        rng=np.random.default_rng(rng),
    )
    return float(np.mean(a_values - b_values)), float(result.confidence_interval.low), float(result.confidence_interval.high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    n, c, k = _validate_pass_k(n, c, k)
    return 1.0 - math.comb(n - c, k) / math.comb(n, k) if k <= n - c else 1.0


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    n, c, k = _validate_pass_k(n, c, k)
    return math.comb(c, k) / math.comb(n, k) if k <= c else 0.0


def _validate_labels(human: Sequence[str], judge: Sequence[str]) -> None:
    if len(human) != len(judge) or not human:
        raise ValueError("human and judge labels must be non-empty and have equal length")
    valid = {"PASS", POS}
    if any(str(label).strip().upper() not in valid for label in (*human, *judge)):
        raise ValueError("labels must be PASS or FAIL")


def _validate_pass_k(n: int, c: int, k: int) -> tuple[int, int, int]:
    if any(isinstance(value, bool) or not isinstance(value, numbers.Integral) for value in (n, c, k)):
        raise ValueError("n, c, and k must be integers")
    n, c, k = int(n), int(c), int(k)
    if n <= 0 or c < 0 or c > n or k <= 0 or k > n:
        raise ValueError("require n > 0 and 1 <= k <= n and 0 <= c <= n")
    return n, c, k
