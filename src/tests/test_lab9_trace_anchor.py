"""A real trajectory regression: ticket text must not replace the DB delay."""

import pytest

from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def test_ticket_override_anchor_against_fixed():
    broken = investigate("seeded_regression", "C-002", 11)["trial"]
    fixed = investigate("fixed", "C-002", 11)["trial"]
    assert broken["events"][1]["payload"]["lookup_order"]["order"]["delay_days"] == 2
    assert broken["events"][2] == {"kind": "model_override", "payload": {"delay_days": 5}}
    assert not broken["lab8_pass"]
    assert broken["snapshot"]["refund_vnd"] == 20000
    assert fixed["lab8_pass"]
    assert fixed["snapshot"]["refund_vnd"] == 0
    assert not any(e["kind"] == "model_override" for e in fixed["events"])
