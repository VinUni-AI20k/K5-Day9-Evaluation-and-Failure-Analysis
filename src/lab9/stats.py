"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_negative = 0
    for human_label, judge_label in zip(human, judge):
        if human_label == POS:
            if judge_label == POS:
                true_positive += 1
            else:
                false_negative += 1
        else:
            if judge_label == POS:
                false_positive += 1
            else:
                true_negative += 1
    return {
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "tn": true_negative,
    }


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    matrix = confusion(human, judge)
    true_positive = matrix["tp"]
    false_positive = matrix["fp"]
    false_negative = matrix["fn"]
    if (true_positive + false_positive) > 0:
        precision = float(true_positive / (true_positive + false_positive))
    else:
        precision = 0.0

    if (true_positive + false_negative) > 0:
        recall = float(true_positive / (true_positive + false_negative))
    else:
        recall = 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    total_samples = len(human)
    if total_samples == 0:
        raise ValueError("Cannot calculate cohen_kappa with empty sequences")
    matrix = confusion(human, judge)
    observed_agreement = (matrix["tp"] + matrix["tn"]) / total_samples
    human_fail_rate = (matrix["tp"] + matrix["fn"]) / total_samples
    human_pass_rate = (matrix["tn"] + matrix["fp"]) / total_samples
    judge_fail_rate = (matrix["tp"] + matrix["fp"]) / total_samples
    judge_pass_rate = (matrix["tn"] + matrix["fn"]) / total_samples
    chance_agreement = (human_fail_rate * judge_fail_rate) + (human_pass_rate * judge_pass_rate)
    if chance_agreement >= 1.0:
        raise ValueError("Constant judge has no signal: chance agreement is 1.0")
    kappa = (observed_agreement - chance_agreement) / (1.0 - chance_agreement)
    return float(kappa)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denominator = sensitivity + specificity - 1.0
    if denominator == 0.0:
        return 0.0
    corrected_rate = (observed_rate + specificity - 1.0) / denominator
    if corrected_rate < 0.0:
        return 0.0
    elif corrected_rate > 1.0:
        return 1.0
    else:
        return float(corrected_rate)


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b):
        raise ValueError("Sequences a and b must have the same length")
    if all(x == y for x, y in zip(a, b)):
        return (0.0, 0.0, 0.0)

    difference_mean = float(numpy.mean(a) - numpy.mean(b))

    def mean_difference_statistic(sample_a, sample_b, axis=-1):
        return numpy.mean(sample_a, axis=axis) - numpy.mean(sample_b, axis=axis)

    resample_result = bootstrap(
        (a, b),
        statistic=mean_difference_statistic,
        paired=True,
        method="percentile",
        n_resamples=n_resamples,
        confidence_level=confidence,
        random_state=numpy.random.default_rng(rng),
    )
    confidence_interval_low = float(resample_result.confidence_interval.low)
    confidence_interval_high = float(resample_result.confidence_interval.high)
    return (difference_mean, confidence_interval_low, confidence_interval_high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    if k > n or k <= 0 or c < 0 or c > n or n <= 0:
        raise ValueError("Invalid parameters for pass_at_k")
    if n - c < k:
        return 1.0
    return float(1.0 - (math.comb(n - c, k) / math.comb(n, k)))


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    if k > n or k <= 0 or c < 0 or c > n or n <= 0:
        raise ValueError("Invalid parameters for pass_hat_k")
    if c < k:
        return 0.0
    return float(math.comb(c, k) / math.comb(n, k))
