"""Bonus: the Inspect AI port's own amount parser agrees with lab9.graders on reply formats.
Skipped when inspect_ai is not installed (CI installs only requirements*-lab9)."""
import pytest

pytest.importorskip("inspect_ai")
pytestmark = pytest.mark.student


@pytest.mark.parametrize("text,want", [
    ("Dạ, LogiX đã hoàn 35.000đ cho đơn O-107.", [35000]),
    ("LogiX đã hoàn phí 20.000đ cho đơn O-808 của anh/chị ạ.", [20000]),
    ("Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành.", []),
    ("Đã hoàn 35k và 1,2 triệu đồng", [35000, 1200000]),
])
def test_lab9_bonus_inspect_amounts(text, want):
    from lab9.graders import reply_amounts
    from lab9.inspect_port import _amounts
    assert _amounts(text) == want
    assert reply_amounts([{"kind": "reply", "payload": {"text": text}}]) == want
