"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
     # TODO M2:
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    for h, j in zip(human, judge):
        if h not in ("PASS", "FAIL") or j not in ("PASS", "FAIL"):
            raise ValueError("labels must be PASS or FAIL")
        if h == POS and j == POS:
            counts["tp"] += 1
        elif h != POS and j == POS:
            counts["fp"] += 1
        elif h == POS and j != POS:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    # TODO M2: precision = tp/(tp+fp), recall = tp/(tp+fn); return 0.0 when the denominator is 0
    counts= confusion(human, judge)
    tp = counts["tp"]
    fp = counts["fp"]
    fn = counts["fn"]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall

def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    # TODO M2
    counts = confusion(human, judge)
    tp, fp, fn, tn = (counts[key] for key in ("tp", "fp", "fn", "tn"))
    total = tp + fp + fn + tn
    if total == 0:
        raise ValueError("kappa is undefined for empty inputs")
    observed = (tp + tn) / total
    expected = (
        (tp + fn) * (tp + fp)
        + (fp + tn) * (fn + tn)
    ) / (total * total)
    if expected == 1:
        raise ValueError("kappa is undefined when expected agreement is 1")
    return (observed - expected) / (1 - expected)
def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    # TODO M2: (p_obs + spec - 1) / (sens + spec - 1)
    denominator = sensitivity + specificity - 1
    if denominator <= 0:
        raise ValueError("sensitivity and specificity must sum to more than 1")

    corrected = (observed_rate + specificity - 1) / denominator
    return max(0.0, min(1.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    # TODO M4
    import numpy as np
    from scipy.stats import bootstrap

    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) != len(b) or len(a) == 0:
        raise ValueError("a and b must have the same nonzero length")
    if np.array_equal(a, b):
        return 0.0, 0.0, 0.0
    difference = float(np.mean(a) - np.mean(b))
    result = bootstrap(
        (a, b),
        statistic=lambda x, y, axis: np.mean(x - y, axis=axis),
        paired=True,
        vectorized=True,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="percentile",
        rng=np.random.default_rng(rng),
    )
    return difference, float(result.confidence_interval.low), float(result.confidence_interval.high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    # TODO M6
    from math import comb

    if not all(isinstance(x, int) and not isinstance(x, bool) for x in (n, c, k)):
        raise ValueError("n, c and k must be integers")
    if n < 1 or c < 0 or c > n or k < 1 or k > n:
        raise ValueError("require n >= 1, 0 <= c <= n and 1 <= k <= n")
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    # TODO M6
    from math import comb

    if not all(isinstance(x, int) and not isinstance(x, bool) for x in (n, c, k)):
        raise ValueError("n, c and k must be integers")
    if n < 1 or c < 0 or c > n or k < 1 or k > n:
        raise ValueError("require n >= 1, 0 <= c <= n and 1 <= k <= n")
    if c < k:
        return 0.0
    return comb(c, k) / comb(n, k)
