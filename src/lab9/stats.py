
"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")

    tp = fp = fn = tn = 0

    for h, j in zip(human, judge):
        if h == POS and j == POS:
            tp += 1
        elif h != POS and j == POS:
            fp += 1
        elif h == POS and j != POS:
            fn += 1
        else:
            tn += 1

    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """Calculate precision and recall, using FAIL as the positive class."""
    counts = confusion(human, judge)

    tp = counts["tp"]
    fp = counts["fp"]
    fn = counts["fn"]

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")

    n = len(human)
    if n == 0:
        raise ValueError("Cohen's kappa requires at least one observation")

    observed = sum(h == j for h, j in zip(human, judge)) / n

    human_pos = sum(h == POS for h in human) / n
    judge_pos = sum(j == POS for j in judge) / n

    expected = (
        human_pos * judge_pos
        + (1 - human_pos) * (1 - judge_pos)
    )

    if np.isclose(expected, 1.0):
        raise ValueError("Cohen's kappa is undefined when expected agreement is 1")

    return (observed - expected) / (1 - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denominator = sensitivity + specificity - 1

    if np.isclose(denominator, 0.0):
        raise ValueError("Sensitivity + specificity must not equal 1")

    corrected = (observed_rate + specificity - 1) / denominator

    return float(np.clip(corrected, 0.0, 1.0))


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_resamples: int = 1000,
    rng: int = 2027,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Return mean(a)-mean(b) and its paired percentile bootstrap CI."""
    a_array = np.asarray(a, dtype=float)
    b_array = np.asarray(b, dtype=float)

    if a_array.ndim != 1 or b_array.ndim != 1:
        raise ValueError("a and b must be one-dimensional")
    if len(a_array) != len(b_array):
        raise ValueError("a and b must have the same length")
    if len(a_array) == 0:
        raise ValueError("a and b must not be empty")
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    if np.array_equal(a_array, b_array):
        return (0.0, 0.0, 0.0)

    difference = float(np.mean(a_array) - np.mean(b_array))

    result = bootstrap(
        (a_array, b_array),
        lambda x, y: np.mean(x - y),
        paired=True,
        vectorized=False,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="percentile",
        rng=np.random.default_rng(rng),
    )

    return (
        difference,
        float(result.confidence_interval.low),
        float(result.confidence_interval.high),
    )


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that at least one of k trials passes."""
    import math

    if not (0 <= c <= n):
        raise ValueError("c must be between 0 and n")
    if not (1 <= k <= n):
        raise ValueError("k must be between 1 and n")

    return 1.0 - math.comb(n - c, k) / math.comb(n, k) if n - c >= k else 1.0


def pass_hat_k(n: int, c: int, k: int) -> float:
    """Probability that all k trials pass."""
    import math

    if not (0 <= c <= n):
        raise ValueError("c must be between 0 and n")
    if not (1 <= k <= n):
        raise ValueError("k must be between 1 and n")

    return math.comb(c, k) / math.comb(n, k) if c >= k else 0.0