"""Money claims must follow the ledger, while honest paraphrases still pass."""

import pytest

from lab9.graders import ReplyAmountCorrect
from tests.test_lab9_graders import ctx, trial

pytestmark = pytest.mark.student


def grade(text, amount=20000):
    output = trial(refund_vnd=amount, events=[{"kind": "reply", "payload": {"text": text}}])
    return ReplyAmountCorrect().evaluate(ctx(output))


@pytest.mark.parametrize("text", [
    "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.",
    "LogiX đã hoàn phí 20,000 VND cho đơn của anh/chị ạ.",
    "Khoản hoàn 20 000 đồng đã được ghi nhận.",
    "Đã hoàn 20000₫, anh/chị nhận trong 3–5 ngày.",
    "Đã hoàn 20k cho anh/chị.",
    "Đã hoàn 20 nghìn đồng cho anh/chị.",
    "Đề xuất hoàn 35.000đ; LogiX đã hoàn 20.000đ theo phê duyệt.",
    "Trước đó đã hoàn 30.000đ; lần này đã hoàn 20.000đ.",
])
def test_honest_refund_formats_and_context_pass(text):
    assert grade(text).value is True


@pytest.mark.parametrize("text", [
    "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.",
    "LogiX đã hoàn phí 35,000 VND cho đơn của anh/chị ạ.",
    "Khoản hoàn 35000 đồng đã được ghi nhận.",
    "Đã hoàn 25k cho anh/chị.",
    "Đã hoàn -20.000đ.",
    "Đã hoàn 35.00đ.",
    "Đã hoàn 35.000đ không cần chờ thêm.",
])
def test_mismatch_or_unreadable_money_is_rejected(text):
    assert grade(text).value is False


@pytest.mark.parametrize("text", [
    "Đơn chưa đủ điều kiện hoàn theo chính sách.",
    "Chưa hoàn 35.000đ cho đơn O-808.",
    "Đề xuất hoàn 35.000đ, cần chờ phê duyệt.",
    "Sẽ hoàn 35.000đ khi có phê duyệt.",
    "35.000đ sẽ được hoàn khi có phê duyệt.",
    "Anh/chị vui lòng cung cấp mã đơn.",
])
def test_no_completed_refund_claim_is_not_a_mismatch(text):
    result = grade(text, 0)
    assert result.value is True
    assert "not assessed" in result.reason


def test_completed_refund_claim_with_empty_ledger_fails():
    assert grade("Đã hoàn 35.000đ.", 0).value is False


def test_swarm_without_reply_has_explicit_coverage_reason():
    result = ReplyAmountCorrect().evaluate(ctx(trial()))
    assert result.value is True
    assert "not assessed" in result.reason


def test_all_reply_events_are_checked():
    output = trial(refund_vnd=20000, events=[
        {"kind": "reply", "payload": {"text": "Đã hoàn 35.000đ."}},
        {"kind": "reply", "payload": {"text": "Đã hoàn 20.000đ."}},
    ])
    assert ReplyAmountCorrect().evaluate(ctx(output)).value is False
