"""Train and evaluate the DistilBERT product/issue classifier (Pair A, stage 1).

Usage (from repo root; GPU strongly recommended, e.g. Colab T4):
    python scripts/train_classifier.py --label product
    python scripts/train_classifier.py --label issue
    python scripts/train_classifier.py --label product --max-train 2000 --max-eval 500 --epochs 1   # smoke test
    python scripts/train_classifier.py --label product --resume   # continue after a disconnect

Reads data/processed/{train,val,test}.parquet (from scripts/run_data_pipeline.py).
Writes to --out (default outputs/classifier/<label>/):
    metrics_{val,test}.json, classification_report_{val,test}.csv,
    confusion_matrix_{val,test}.csv/.png, predictions_{val,test}.parquet,
    run_info.json (args, labels, per-epoch history, versions, GPU),
    best/ (best-on-validation model), last/ (latest checkpoint for --resume)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.classify.data import load_split  # noqa: E402
from cfpb.classify.train import train  # noqa: E402
from cfpb.config import OUTPUT_DIR, PROCESSED_DIR, RANDOM_SEED  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", choices=["product", "issue"], default="product")
    ap.add_argument("--data-dir", type=Path, default=PROCESSED_DIR)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--model", default="distilbert-base-uncased")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32, help="lower to 16 if CUDA runs out of memory")
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--warmup", type=float, default=0.06, help="fraction of total steps")
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--max-len", type=int, default=512)
    ap.add_argument("--head-tokens", type=int, default=128,
                    help="tokens kept from the start of long narratives; rest from the end. "
                         "Use 512 for head-only truncation")
    ap.add_argument("--class-weights", action="store_true",
                    help="inverse-sqrt-frequency loss weights (try if small classes lag)")
    ap.add_argument("--max-train", type=int, default=None, help="subsample train (smoke tests)")
    ap.add_argument("--max-eval", type=int, default=None, help="subsample val and test (smoke tests)")
    ap.add_argument("--resume", action="store_true", help="continue from <out>/last if present")
    ap.add_argument("--log-every", type=int, default=200)
    ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = ap.parse_args()
    args.out = args.out or OUTPUT_DIR / "classifier" / args.label

    dfs = {}
    for split, cap in [("train", args.max_train), ("val", args.max_eval), ("test", args.max_eval)]:
        path = args.data_dir / f"{split}.parquet"
        if not path.exists():
            sys.exit(f"Missing {path}. Run scripts/run_data_pipeline.py first.")
        dfs[split] = load_split(path, args.label, cap, args.seed)
    print({k: len(v) for k, v in dfs.items()}, f"label={args.label}",
          f"classes={dfs['train'][args.label].nunique()}")

    results = train(args, dfs["train"], dfs["val"], dfs["test"])
    print(json.dumps(results, indent=2))
    print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
