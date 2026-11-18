"""M6 estimators checked against all subsets, invalid inputs and rare events."""

from itertools import combinations

import pytest

from lab9 import stats

pytestmark = pytest.mark.student


def test_pass_k_matches_exhaustive_sampling_without_replacement():
    for n in range(1, 8):
        for c in range(n + 1):
            trials = [True] * c + [False] * (n - c)
            for k in range(1, n + 1):
                samples = list(combinations(trials, k))
                assert stats.pass_at_k(n, c, k) == pytest.approx(sum(any(s) for s in samples) / len(samples))
                assert stats.pass_hat_k(n, c, k) == pytest.approx(sum(all(s) for s in samples) / len(samples))
                assert 0 <= stats.pass_hat_k(n, c, k) <= c / n <= stats.pass_at_k(n, c, k) <= 1


@pytest.mark.parametrize("args", [
    (0, 0, 0), (0, 0, 1), (-1, 0, 1), (5, -1, 1), (5, 6, 1),
    (5, 2, 0), (3, 1, 4), (5.0, 2, 1), (5, 2.0, 1), (5, 2, 1.5),
    (True, 1, 1), (5, False, 1), (5, 2, True), ("5", 2, 1), (5, None, 1),
])
def test_both_estimators_reject_invalid_counts(args):
    for estimator in (stats.pass_at_k, stats.pass_hat_k):
        with pytest.raises(ValueError):
            estimator(*args)


def test_five_trials_distinguish_reliability_from_eventual_success():
    assert stats.pass_at_k(5, 4, 5) == 1.0
    assert stats.pass_hat_k(5, 4, 5) == 0.0


def test_rare_success_does_not_disappear_through_float_cancellation():
    assert stats.pass_at_k(10**18, 1, 3) == pytest.approx(3e-18, rel=1e-12, abs=0)


def test_numpy_integer_counts_are_supported():
    import numpy as np
    assert stats.pass_at_k(np.int64(5), np.int64(2), np.int64(1)) == 0.4
    assert stats.pass_hat_k(np.int64(5), np.int64(4), np.int64(3)) == 0.4


def test_report_aggregates_reliability_per_item():
    from lab9.eval import aggregate

    rows = [{"item_id": item, "seed": seed, "pass_rate": seed < successes, "cost": 1.0}
            for item, successes in (("sometimes", 4), ("always", 5)) for seed in range(5)]
    metrics = aggregate(rows, ["pass_rate"], k_values=[1, 3, 5])
    assert metrics["pass_rate"] == metrics["pass_at_1"] == metrics["pass_hat_1"] == 0.9
    assert metrics["pass_at_5"] == 1.0
    assert metrics["pass_hat_3"] == 0.7
    assert metrics["pass_hat_5"] == metrics["pass_5"] == 0.5
