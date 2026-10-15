"""Re-score a finished classifier run WITHOUT retraining.

    python scripts/evaluate_classifier.py --run outputs/classifier/product
    python scripts/evaluate_classifier.py --run outputs/classifier/issue
    python scripts/evaluate_classifier.py --run outputs/classifier/product --repredict   # reload best/ model

Default: recompute metrics, reports and confusion matrices from the saved
predictions_{val,test}.parquet (seconds, no GPU). Use after changing how
metrics are computed (e.g. the 2026-10-15 macro-F1 convention fix).

--repredict: load <run>/best and predict val/test again from
data/processed (needs the model weights; slow on CPU, minutes on GPU). Use if
you only have the model, or to verify a model reproduces its saved outputs.

Updates <run>/run_info.json "results" and records the rescoring in "rescored".
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.classify.train import compute_metrics, save_reports, summarize  # noqa: E402
from cfpb.config import PROCESSED_DIR  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True, help="folder with run_info.json")
    ap.add_argument("--repredict", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=PROCESSED_DIR)
    args = ap.parse_args()

    info_path = args.run / "run_info.json"
    info = json.loads(info_path.read_text())
    labels, label_col = info["labels"], info["args"]["label"]
    old = json.loads(json.dumps(info.get("results", {})))  # copy: results are overwritten below

    if args.repredict:
        from cfpb.classify.predict import ComplaintClassifier  # torch only needed here
        clf = ComplaintClassifier(args.run / "best")
    for split in ("val", "test"):
        pred_path = args.run / f"predictions_{split}.parquet"
        if args.repredict:
            df = pd.read_parquet(args.data_dir / f"{split}.parquet",
                                 columns=["complaint_id", "narrative_clean", label_col])
            probs = clf.predict_proba(df["narrative_clean"], clean=False)
            preds = pd.DataFrame({
                "complaint_id": df["complaint_id"].values,
                f"true_{label_col}": df[label_col].values,
                f"pred_{label_col}": [clf.labels[i] for i in probs.argmax(1)],
                f"pred_{label_col}_prob": probs.max(1).round(4),
            })
        else:
            preds = pd.read_parquet(pred_path)
        metrics = compute_metrics(preds, labels, label_col)
        save_reports(args.run, split, metrics, preds, labels, label_col)
        info.setdefault("results", {})[split] = summarize(metrics)
        before = old.get(split, {}).get("macro_f1")
        was = f" (was {before:.4f})" if before is not None else ""
        print(f"{label_col} {split}: macro-F1 {metrics['macro_f1']:.4f}{was}",
              f"| all-train-labels {metrics['macro_f1_all_train_labels']:.4f} "
              f"| accuracy {metrics['accuracy']:.4f} | labels scored {metrics['n_labels_scored']}"
              f" | without examples: {metrics['labels_without_examples']}")

    info.setdefault("rescored", []).append({
        "at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "repredict" if args.repredict else "from saved predictions",
        "macro_f1_convention": "labels present in true or predicted labels of the split",
    })
    info_path.write_text(json.dumps(info, indent=2, default=str))
    print(f"Updated {args.run}")


if __name__ == "__main__":
    main()
