"""Statistics: M2 judge calibration, M4 paired bootstrap, M6 pass-k estimators.

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb, isfinite
from numbers import Integral

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same number of labels")
    counts = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
    for actual, predicted in zip(human, judge):
        if actual not in ("PASS", "FAIL") or predicted not in ("PASS", "FAIL"):
            raise ValueError("labels must be PASS or FAIL")
        key = ("tp" if actual == POS else "fp") if predicted == POS else (
            "fn" if actual == POS else "tn"
        )
        counts[key] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    predicted_fail = cm["tp"] + cm["fp"]
    actual_fail = cm["tp"] + cm["fn"]
    return (cm["tp"] / predicted_fail if predicted_fail else 0.0,
            cm["tp"] / actual_fail if actual_fail else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if not n:
        raise ValueError("kappa is undefined without labels")
    # Work with integer counts until the division to detect p_e == 1 exactly.
    expected_agreement = ((cm["tp"] + cm["fn"]) * (cm["tp"] + cm["fp"])
                          + (cm["tn"] + cm["fp"]) * (cm["tn"] + cm["fn"]))
    denominator = n * n - expected_agreement
    if denominator == 0:
        raise ValueError("kappa is undefined when chance agreement is 1")
    return (n * (cm["tp"] + cm["tn"]) - expected_agreement) / denominator


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    if any(not isfinite(v) or not 0 <= v <= 1
           for v in (observed_rate, sensitivity, specificity)):
        raise ValueError("rates must be finite numbers in [0, 1]")
    denominator = sensitivity + specificity - 1
    if denominator == 0:
        raise ValueError("Rogan-Gladen is undefined when sensitivity + specificity == 1")
    corrected = (observed_rate + specificity - 1) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    left, right = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if left.ndim != 1 or right.ndim != 1 or left.shape != right.shape or not left.size:
        raise ValueError("paired samples must be nonempty 1-D vectors of the same length")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("paired samples must contain only finite numbers")
    if not 0 < confidence < 1 or not isinstance(n_resamples, int) or n_resamples < 1:
        raise ValueError("confidence must be in (0, 1) and n_resamples a positive integer")
    delta = float(np.mean(left - right))
    if np.array_equal(left, right):
        return 0.0, 0.0, 0.0
    if left.size < 2:
        raise ValueError("bootstrap requires at least two paired items")

    def difference(x, y, axis=-1):
        return np.mean(x - y, axis=axis)

    result = bootstrap((left, right), difference, paired=True, vectorized=True,
                       n_resamples=n_resamples, confidence_level=confidence,
                       method="percentile", rng=np.random.default_rng(rng))
    return delta, float(result.confidence_interval.low), float(result.confidence_interval.high)


def _pass_k_args(n: int, c: int, k: int) -> tuple[int, int, int]:
    if any(isinstance(v, bool) or not isinstance(v, Integral) for v in (n, c, k)):
        raise ValueError("n, c, k must be integers (not booleans)")
    n, c, k = int(n), int(c), int(k)
    if n < 1 or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("require n >= 1, 0 <= c <= n and 1 <= k <= n")
    return n, c, k


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    n, c, k = _pass_k_args(n, c, k)
    if n - c < k:
        return 1.0
    denominator = comb(n, k)
    # Subtract exact integer counts before division to avoid cancellation when
    # a passing trial is very rare (1 - a nearly-one float can round to zero).
    return (denominator - comb(n - c, k)) / denominator


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    n, c, k = _pass_k_args(n, c, k)
    return comb(c, k) / comb(n, k) if c >= k else 0.0
