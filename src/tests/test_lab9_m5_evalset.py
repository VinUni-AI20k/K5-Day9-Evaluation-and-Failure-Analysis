"""M5 dataset contract: preserve v1, cover attacks and keep label-derived slices."""

from collections import Counter
import json
from pathlib import Path

import pytest

from lab9 import evalset

pytestmark = pytest.mark.student


def data():
    return (evalset.load_jsonl(evalset.ITEMS_V2),
            json.loads(evalset.LABELS_V2.read_text(encoding="utf-8")))


def test_v2_preserves_every_v1_claim_and_adds_the_complete_pack():
    items, labels = data()
    v1 = evalset.load_jsonl(evalset.ITEMS)
    pack = json.loads(evalset.PACK.read_text(encoding="utf-8"))
    assert len(items) == len(v1) + len(pack["claims"])
    assert {i["claim_id"] for i in items} == {i["claim_id"] for i in v1 + pack["claims"]}
    old_labels = json.loads(evalset.LABELS.read_text(encoding="utf-8"))
    assert all(labels[k] == v for k, v in old_labels.items())
    for old in v1:
        new = next(i for i in items if i["item_id"] == old["item_id"])
        assert {k: new[k] for k in old if k != "eval_set_version"} == {
            k: v for k, v in old.items() if k != "eval_set_version"
        }


def test_v2_attack_coverage_and_separate_labels():
    items, labels = data()
    attacked = {fm for item in items if item["split"] == "adversarial" for fm in item["failure_modes"]}
    counts = Counter(fm for item in items for fm in set(item["failure_modes"]))
    assert all(counts[fm] >= 3 for fm in attacked)
    assert all(evalset.FM_CODE.fullmatch(fm) for fm in attacked)
    assert all("expected" not in i and "label" not in i and i["claim_id"] in labels for i in items)
    assert evalset.check(evalset.ITEMS_V2, evalset.LABELS_V2) == []


def test_v2_slice_tags_come_from_labels_and_split():
    items, labels = data()
    for item in items:
        tags = set(item["slices"])
        label = labels[item["claim_id"]]
        assert ("money_movement" in tags) == (label["refund_vnd"] > 0)
        assert ("adversarial" in tags) == (item["split"] == "adversarial")
        assert ("denial" in tags) == (label["status"] == "denied")
        assert ("escalation" in tags) == (label["status"] == "escalated")


def test_v2_generated_files_have_platform_independent_line_endings():
    assert b"\r" not in evalset.ITEMS_V2.read_bytes()
    assert b"\r" not in evalset.LABELS_V2.read_bytes()


@pytest.mark.parametrize("mutation", ["unmapped", "missing_pack_claim", "insufficient_fm_coverage"])
def test_v2_checker_rejects_broken_attack_coverage(tmp_path, mutation):
    items, labels = data()
    if mutation == "unmapped":
        next(i for i in items if i["split"] == "adversarial")["failure_modes"] = ["UNMAPPED:ticket_over_db"]
        expected = "UNMAPPED:ticket_over_db"
    elif mutation == "missing_pack_claim":
        items = [i for i in items if i["claim_id"] != "C-101"]
        expected = "C-101: adversarial claim missing"
    else:
        kept = False
        for item in items:
            if "FM-09" in item["failure_modes"]:
                if kept:
                    item["failure_modes"].remove("FM-09")
                kept = True
        expected = "FM-09: only 1 item(s)"
    path, lp = tmp_path / "items.jsonl", tmp_path / "labels.json"
    path.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")
    lp.write_text(json.dumps(labels), encoding="utf-8")
    assert any(expected in problem for problem in evalset.check(path, lp))
