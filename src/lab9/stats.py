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
    tp = fp = fn = tn = 0
    for h, j in zip(human, judge):
        h_pos = (h == POS)
        j_pos = (j == POS)
        if h_pos and j_pos:
            tp += 1
        elif not h_pos and j_pos:
            fp += 1
        elif h_pos and not j_pos:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return prec, rec


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    n = len(human)
    if n == 0:
        raise ValueError("Empty sequence")
    agree = sum(1 for h, j in zip(human, judge) if h == j)
    p_o = agree / n
    categories = set(human) | set(judge)
    p_e = 0.0
    for cat in categories:
        p_h = sum(1 for h in human if h == cat) / n
        p_j = sum(1 for j in judge if j == cat) / n
        p_e += p_h * p_j
    if abs(1.0 - p_e) < 1e-12:
        raise ValueError("p_e == 1, Cohen's kappa is undefined")
    return (p_o - p_e) / (1.0 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = sensitivity + specificity - 1.0
    if abs(denom) < 1e-12:
        return max(0.0, min(1.0, observed_rate))
    corrected = (observed_rate + specificity - 1.0) / denom
    return max(0.0, min(1.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    a_arr = np.array(list(a), dtype=float)
    b_arr = np.array(list(b), dtype=float)

    if a_arr.ndim != 1 or b_arr.ndim != 1 or a_arr.shape != b_arr.shape or a_arr.size == 0:
        raise ValueError("Paired samples must be non-empty one-dimensional sequences of equal length")
    if not np.isfinite(a_arr).all() or not np.isfinite(b_arr).all():
        raise ValueError("Paired samples must contain finite values")

    if np.array_equal(a_arr, b_arr):
        return (0.0, 0.0, 0.0)

    diffs = a_arr - b_arr
    mean_d = float(np.mean(diffs))

    res = bootstrap(
        (a_arr, b_arr),
        lambda x, y, axis: np.mean(x - y, axis=axis),
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="percentile",
        paired=True,
        rng=np.random.default_rng(rng),
    )
    return (mean_d, float(res.confidence_interval.low), float(res.confidence_interval.high))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    from math import comb

    if not all(isinstance(value, int) for value in (n, c, k)) or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("Require integer arguments with 0 <= c <= n and 1 <= k <= n")
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    from math import comb

    if not all(isinstance(value, int) for value in (n, c, k)) or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("Require integer arguments with 0 <= c <= n and 1 <= k <= n")
    return comb(c, k) / comb(n, k)
