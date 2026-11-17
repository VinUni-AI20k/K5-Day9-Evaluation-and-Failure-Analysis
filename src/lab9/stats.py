"""Statistics for M2 judge calibration, M4 paired bootstrap, and M6 pass@k/pass^k.

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from math import comb
from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same number of labels")
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(human, judge):
        if h not in {"PASS", POS} or j not in {"PASS", POS}:
            raise ValueError(f"expected PASS or FAIL labels, got {h!r} and {j!r}")
        if h == POS:
            counts["tp" if j == POS else "fn"] += 1
        else:
            counts["fp" if j == POS else "tn"] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    predicted_fail = cm["tp"] + cm["fp"]
    actual_fail = cm["tp"] + cm["fn"]
    precision = cm["tp"] / predicted_fail if predicted_fail else 0.0
    recall = cm["tp"] / actual_fail if actual_fail else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa is undefined for empty labels")
    observed = (cm["tp"] + cm["tn"]) / n
    expected = ((cm["tp"] + cm["fn"]) * (cm["tp"] + cm["fp"])
                + (cm["fp"] + cm["tn"]) * (cm["fn"] + cm["tn"])) / (n * n)
    if expected == 1:
        raise ValueError("kappa is undefined when chance agreement is 1")
    return (observed - expected) / (1 - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denominator = sensitivity + specificity - 1
    if denominator == 0:
        raise ValueError("Rogan-Gladen correction is undefined when sensitivity + specificity = 1")
    corrected = (observed_rate + specificity - 1) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    if len(a) != len(b) or not a:
        raise ValueError("paired_bootstrap requires non-empty samples of equal length")
    if n_resamples <= 0 or not 0 < confidence < 1:
        raise ValueError("n_resamples must be positive and confidence must be between 0 and 1")
    left = np.asarray(a, dtype=float)
    right = np.asarray(b, dtype=float)
    if not (np.isfinite(left).all() and np.isfinite(right).all()):
        raise ValueError("paired_bootstrap requires finite values")
    if np.array_equal(left, right):
        return (0.0, 0.0, 0.0)

    def difference(x: np.ndarray, y: np.ndarray, axis: int = 0) -> np.ndarray:
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)

    ci = bootstrap((left, right), difference, paired=True, vectorized=True,
                   method="percentile", n_resamples=n_resamples,
                   confidence_level=confidence, rng=np.random.default_rng(rng)).confidence_interval
    return (float(difference(left, right)), float(ci.low), float(ci.high))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_pass_k(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_pass_k(n, c, k)
    if c < k:
        return 0.0
    return comb(c, k) / comb(n, k)


def _validate_pass_k(n: int, c: int, k: int) -> None:
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (n, c, k)):
        raise ValueError("n, c and k must be integers")
    if n <= 0 or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("require n > 0, 0 <= c <= n and 1 <= k <= n")
