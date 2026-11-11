import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

torch = pytest.importorskip("torch")  # classifier deps are optional for data-only setups

from cfpb.classify.data import collate, encode, length_bucketed_batches  # noqa: E402


class FakeTokenizer:
    """One token per word; ids are word lengths. CLS=101, SEP=102."""
    cls_token_id, sep_token_id = 101, 102

    def __call__(self, texts, add_special_tokens, truncation):
        return {"input_ids": [[len(w) for w in t.split()] for t in texts]}


def test_short_text_untouched():
    assert encode(["a bb ccc"], FakeTokenizer(), max_len=10, head=2) == [[101, 1, 2, 3, 102]]


def test_head_tail_truncation():
    text = " ".join("x" * n for n in range(1, 21))  # token ids 1..20
    out = encode([text], FakeTokenizer(), max_len=8, head=2)[0]
    assert out == [101, 1, 2, 17, 18, 19, 20, 102]  # 2 head + 4 tail + specials = 8


def test_head_only_truncation():
    text = " ".join("x" * n for n in range(1, 21))
    out = encode([text], FakeTokenizer(), max_len=8, head=512)[0]
    assert out == [101, 1, 2, 3, 4, 5, 6, 102]


def test_batches_cover_every_example_once():
    lengths = [5, 1, 9, 3, 7, 2, 8]
    batches = length_bucketed_batches(lengths, batch_size=3, seed=0)
    assert sorted(i for b in batches for i in b) == list(range(len(lengths)))


def test_collate_pads_and_masks():
    out = collate([[101, 5, 102], [101, 102]], [1, 0], pad_id=0)
    assert out["input_ids"].tolist() == [[101, 5, 102], [101, 102, 0]]
    assert out["attention_mask"].tolist() == [[1, 1, 1], [1, 1, 0]]
    assert out["labels"].tolist() == [1, 0]
