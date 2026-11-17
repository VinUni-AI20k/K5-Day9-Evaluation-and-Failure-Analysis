"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    tp = fp = fn = tn = 0
    for actual, predicted in zip(human, judge):
        actual_fail, predicted_fail = actual == POS, predicted == POS
        if actual_fail and predicted_fail:
            tp += 1
        elif predicted_fail:
            fp += 1
        elif actual_fail:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    if len(human) != len(judge) or not human:
        raise ValueError("kappa requires equally sized, non-empty label sequences")
    n = len(human)
    observed = sum(a == b for a, b in zip(human, judge)) / n
    labels = set(human) | set(judge)
    expected = sum((sum(x == label for x in human) / n) *
                   (sum(x == label for x in judge) / n) for label in labels)
    if expected == 1:
        raise ValueError("Cohen's kappa is undefined when expected agreement is 1")
    return (observed - expected) / (1 - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denominator = sensitivity + specificity - 1
    if denominator == 0:
        raise ValueError("sensitivity + specificity must not equal 1")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denominator))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    if len(a) != len(b) or not a:
        raise ValueError("paired bootstrap requires equally sized, non-empty samples")
    if n_resamples < 1 or not 0 < confidence < 1:
        raise ValueError("n_resamples must be positive and confidence must be in (0, 1)")
    left, right = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    delta = float(np.mean(left - right))
    if np.all(left == right):
        return 0.0, 0.0, 0.0
    result = bootstrap((left, right), lambda x, y, axis: np.mean(x - y, axis=axis),
                       paired=True, vectorized=True, n_resamples=n_resamples,
                       confidence_level=confidence, method="percentile",
                       rng=np.random.default_rng(rng))
    return delta, float(result.confidence_interval.low), float(result.confidence_interval.high)


def _validate_k(n: int, c: int, k: int) -> None:
    if any(not isinstance(x, int) for x in (n, c, k)) or n <= 0 or not 0 <= c <= n or k <= 0 or k > n:
        raise ValueError("require integers n > 0, 0 <= c <= n, and 1 <= k <= n")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    from math import comb
    _validate_k(n, c, k)
    return 1.0 - (comb(n - c, k) / comb(n, k) if n - c >= k else 0.0)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    from math import comb
    _validate_k(n, c, k)
    return comb(c, k) / comb(n, k) if c >= k else 0.0
