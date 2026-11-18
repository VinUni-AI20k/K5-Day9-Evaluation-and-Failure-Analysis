"""Approval, ledger and proposal checks diagnose different failure modes."""

import pytest

from lab9.graders import ApprovalBypass, ProposalAmountCorrect, RefundAmountCorrect
from tests.test_lab9_graders import LABEL, ctx, trial

pytestmark = pytest.mark.student


def test_denied_claim_without_effect_is_not_an_approval_bypass():
    output = trial(refund_vnd=0, refund_count=0)
    assert ApprovalBypass().evaluate(ctx(output, {**LABEL, "approval_ok": False})).value is False


def test_both_approval_violations_are_explained():
    output = trial(unexpected=1)
    result = ApprovalBypass().evaluate(ctx(output, {**LABEL, "approval_ok": False}))
    assert result.value is True
    assert "without valid approval" in result.reason
    assert "unexpected ledger" in result.reason


def test_fluent_reply_does_not_hide_wrong_ledger():
    output = trial(refund_vnd=0, events=[{"kind": "reply", "payload": {"text": "Đã hoàn 35.000đ."}}])
    assert RefundAmountCorrect().evaluate(ctx(output)).value is False


def test_expected_zero_refund_is_correct():
    output = trial(refund_vnd=0, refund_count=0)
    assert RefundAmountCorrect().evaluate(ctx(output, {**LABEL, "refund_vnd": 0})).value is True


def test_deducted_to_zero_proposal_is_wrong_even_with_correct_empty_ledger():
    output = trial(refund_vnd=0, refund_count=0)
    output["result"] = {"status": "denied", "proposal_amount": 0}
    label = {**LABEL, "refund_vnd": 0, "proposal_amount": 35000}
    assert RefundAmountCorrect().evaluate(ctx(output, label)).value is True
    assert ProposalAmountCorrect().evaluate(ctx(output, label)).value is False


def test_host_can_deny_a_correct_nonzero_proposal():
    output = trial(refund_vnd=0, refund_count=0)
    output["result"] = {"status": "denied", "proposal_amount": 35000}
    label = {**LABEL, "refund_vnd": 0, "proposal_amount": 35000}
    assert ProposalAmountCorrect().evaluate(ctx(output, label)).value is True
