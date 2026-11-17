import pytest

pytestmark = pytest.mark.student


def test_ticket_override_is_first_wrong_step_and_fixed_has_none():
    from lab9.trace_case import investigate

    regression = investigate("seeded_regression", "C-002", 11)["trial"]
    fixed = investigate("fixed", "C-002", 11)["trial"]

    overrides = [
        (index, event)
        for index, event in enumerate(regression["events"], start=1)
        if event.get("kind") == "model_override"
    ]
    assert len(overrides) == 1
    assert overrides[0][0] == 3
    assert overrides[0][1]["payload"]["delay_days"] == 5
    assert not any(event.get("kind") == "model_override" for event in fixed["events"])
    assert regression["snapshot"]["refund_vnd"] == 20000
    assert fixed["snapshot"]["refund_vnd"] == 0

