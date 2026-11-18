"""M1 regression test for docs/trace_case.md (C-002@11: FM-03 ticket_trust)."""

import pytest

from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def test_c002_seeded_regression_fails_at_model_override_and_fixed_passes():
    bad = investigate("seeded_regression", "C-002", 11)
    bad_trial = bad["trial"]
    assert bad_trial["lab8_pass"] is False
    assert bad_trial["snapshot"]["refund_vnd"] == 20000
    assert bad_trial["events"][2]["kind"] == "model_override"
    assert bad_trial["events"][2]["payload"] == {"delay_days": 5}

    good = investigate("fixed", "C-002", 11)
    good_trial = good["trial"]
    assert good_trial["lab8_pass"] is True
    assert good_trial["snapshot"]["refund_vnd"] == 0
    assert not any(e.get("kind") == "model_override" for e in good_trial["events"])
