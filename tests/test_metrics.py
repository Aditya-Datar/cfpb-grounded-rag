import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytest.importorskip("torch")  # train.py imports torch/transformers

from cfpb.classify.train import compute_metrics  # noqa: E402


def _preds(true, pred):
    return pd.DataFrame({"complaint_id": [str(i) for i in range(len(true))],
                         "true_issue": true, "pred_issue": pred})


def test_labels_without_examples_do_not_count_as_zero():
    labels = ["a", "b", "never_seen_in_test"]
    m = compute_metrics(_preds(["a", "a", "b", "b"], ["a", "a", "b", "b"]), labels, "issue")
    assert m["macro_f1"] == 1.0
    assert m["labels_without_examples"] == ["never_seen_in_test"]
    assert m["macro_f1_all_train_labels"] == pytest.approx(2 / 3)


def test_wrongly_predicted_absent_label_still_penalized():
    labels = ["a", "b", "c"]
    m = compute_metrics(_preds(["a", "b"], ["a", "c"]), labels, "issue")  # "c" has no true examples
    assert m["n_labels_scored"] == 3
    assert m["macro_f1"] == pytest.approx(1 / 3)  # a=1, b=0, c=0


def test_unseen_true_labels_excluded_and_counted():
    m = compute_metrics(_preds(["a", "zzz"], ["a", "a"]), ["a", "b"], "issue")
    assert m["n"] == 1 and m["n_excluded_unseen_label"] == 1
