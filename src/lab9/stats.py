"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import scipy.stats as st

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    tp = sum(1 for h, j in zip(human, judge) if h == j == POS)
    fp = sum(1 for h, j in zip(human, judge) if h != POS and j == POS)
    fn = sum(1 for h, j in zip(human, judge) if h == POS and j != POS)
    tn = sum(1 for h, j in zip(human, judge) if h != POS and j != POS)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    # precision = tp/(tp+fp), recall = tp/(tp+fn); 0.0 when the denominator is 0
    tp, fp, fn, tn = confusion(human, judge).values()
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    tp, fp, fn, tn = confusion(human, judge).values()
    n = tp + fp + fn + tn
    if n == 0:
        raise ValueError("kappa undefined for empty sequences")
    # p_e: expected probability that the two sequences agree by chance
    pe = ((tp + fp) * (tp + fn) + (tn + fn) * (tn + fp)) / (n * n)
    po = (tp + tn) / n
    if pe == 1:
        raise ValueError("kappa undefined: the judge agrees with a chance probability of 1 (constant judge)")
    return (po - pe) / (1 - pe)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    # M2: (p_obs + spec - 1) / (sens + spec - 1)
    p_obs, sens, spec = float(observed_rate), float(sensitivity), float(specificity)
    if sens + spec == 1:
        raise ValueError("rogan_gladen undefined: sens + spec == 1")
    p_corr = (p_obs + spec - 1) / (sens + spec - 1)
    return max(0.0, min(1.0, p_corr))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seed, SAME item, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b):
        raise ValueError("paired_bootstrap requires sequences of the same length")
    if len(a) == 0:
        return 0.0, 0.0, 0.0
    if all(math.isclose(float(x), float(y), abs_tol=1e-9) for x, y in zip(a, b)):
        return 0.0, 0.0, 0.0
    a_np = np.array(a, dtype=float)
    b_np = np.array(b, dtype=float)
    d = float(np.mean(a_np) - np.mean(b_np))
    if len(a_np) < 2:                      # bootstrap needs >= 2 paired items; a single item has no spread
        return d, d, d
    ci = st.bootstrap((a_np, b_np), statistic=lambda x, y, axis=-1: np.mean(x, axis=-1) - np.mean(y, axis=-1),
                      paired=True, n_resamples=n_resamples, method="percentile",
                      confidence_level=confidence, rng=np.random.default_rng(rng))
    lo, hi = ci.confidence_interval
    return d, float(lo), float(hi)


def _check_nck(n: int, c: int, k: int) -> None:
    for name, v in (("n", n), ("c", c), ("k", k)):
        if isinstance(v, bool) or not isinstance(v, (int, np.integer)):
            raise ValueError(f"{name} must be an integer, got {v!r}")
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if not 0 <= c <= n:
        raise ValueError(f"c must be in [0, n], got c={c}, n={n}")
    if not 1 <= k <= n:
        raise ValueError(f"k must be in [1, n], got k={k}, n={n}")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _check_nck(n, c, k)
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)   # comb(m, k) = 0 when k > m


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _check_nck(n, c, k)
    return math.comb(c, k) / math.comb(n, k)