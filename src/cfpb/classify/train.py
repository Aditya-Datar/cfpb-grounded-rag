"""Fine-tune and evaluate a DistilBERT classifier on the CFPB splits.

A plain PyTorch loop rather than the HF Trainer: the Trainer's arguments have
changed across transformers releases, and Colab upgrades transformers often.
Only long-stable APIs are used here (AutoModel*, get_linear_schedule_with_warmup).
"""
import copy
import json
import math
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import torch
import transformers
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score)
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          get_linear_schedule_with_warmup)

from cfpb.classify.data import collate, encode, length_bucketed_batches


def pick_device_and_dtype():
    if torch.cuda.is_available():
        # bf16 on A100/L4 (no loss scaling needed); fp16 + GradScaler on T4.
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        return torch.device("cuda"), dtype
    return torch.device("cpu"), None


@torch.no_grad()
def predict(model, enc: list[list[int]], batch_size: int, device, dtype, pad_id: int) -> np.ndarray:
    """Return softmax probabilities, shape (n, num_labels), in input order."""
    model.eval()
    probs = np.zeros((len(enc), model.config.num_labels), dtype=np.float32)
    lengths = [len(x) for x in enc]
    for b in length_bucketed_batches(lengths, batch_size * 2, seed=0, shuffle=False):
        batch = {k: v.to(device) for k, v in collate([enc[i] for i in b], None, pad_id).items()}
        with torch.autocast(device.type, dtype=dtype, enabled=dtype is not None):
            logits = model(**batch).logits
        probs[b] = torch.softmax(logits.float(), dim=-1).cpu().numpy()
    return probs


def evaluate(df: pd.DataFrame, probs: np.ndarray, labels: list[str], label_col: str) -> tuple[dict, pd.DataFrame]:
    """Metrics plus a predictions table. Rows whose true label never appeared in
    train cannot be predicted, so they are excluded from metrics and counted."""
    pred_idx = probs.argmax(1)
    preds = pd.DataFrame({
        "complaint_id": df["complaint_id"].values,
        f"true_{label_col}": df[label_col].values,
        f"pred_{label_col}": [labels[i] for i in pred_idx],
        f"pred_{label_col}_prob": probs.max(1).round(4),
    })
    known = preds[f"true_{label_col}"].isin(labels)
    y_true, y_pred = preds.loc[known, f"true_{label_col}"], preds.loc[known, f"pred_{label_col}"]
    metrics = {
        "n": int(known.sum()),
        "n_excluded_unseen_label": int((~known).sum()),
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0),
        "per_class": classification_report(y_true, y_pred, labels=labels, output_dict=True,
                                           zero_division=0),
    }
    return metrics, preds


def save_reports(out: Path, split: str, metrics: dict, preds: pd.DataFrame,
                 labels: list[str], label_col: str) -> None:
    (out / f"metrics_{split}.json").write_text(json.dumps(metrics, indent=2))
    preds.to_parquet(out / f"predictions_{split}.parquet", index=False)
    rep = pd.DataFrame(metrics["per_class"]).T
    rep.index.name = "class"
    rep.to_csv(out / f"classification_report_{split}.csv")
    known = preds[f"true_{label_col}"].isin(labels)
    cm = confusion_matrix(preds.loc[known, f"true_{label_col}"],
                          preds.loc[known, f"pred_{label_col}"], labels=labels)
    pd.DataFrame(cm, index=labels, columns=labels).to_csv(out / f"confusion_matrix_{split}.csv")
    try:  # plot is optional; matplotlib is preinstalled on Colab
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
        size = max(6, 0.45 * len(labels))
        fig, ax = plt.subplots(figsize=(size, size))
        ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        short = [lab[:40] for lab in labels]
        ax.set_xticks(range(len(labels)), short, rotation=90, fontsize=7)
        ax.set_yticks(range(len(labels)), short, fontsize=7)
        ax.set_xlabel("predicted")
        ax.set_ylabel("true")
        ax.set_title(f"{label_col} confusion ({split}, row-normalized)")
        fig.tight_layout()
        fig.savefig(out / f"confusion_matrix_{split}.png", dpi=150)
        plt.close(fig)
    except ImportError:
        pass


def train(args, train_df, val_df, test_df) -> dict:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed)
    # Silences "sequence longer than 512" from tokenizing full narratives;
    # encode() truncates them afterwards.
    transformers.logging.set_verbosity_error()
    device, dtype = pick_device_and_dtype()
    print(f"device={device} dtype={dtype} torch={torch.__version__} "
          f"transformers={transformers.__version__}")

    label_col = args.label
    labels = sorted(train_df[label_col].unique())
    label2id = {lab: i for i, lab in enumerate(labels)}

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    pad_id = tokenizer.pad_token_id
    t0 = time.time()
    enc = {name: encode(df["narrative_clean"], tokenizer, args.max_len, args.head_tokens)
           for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]}
    trunc = np.mean([len(x) >= args.max_len for x in enc["train"]])
    print(f"tokenized in {time.time() - t0:.0f}s; {trunc:.1%} of train narratives truncated "
          f"to {args.max_len} tokens")
    y_train = [label2id[lab] for lab in train_df[label_col]]

    state_path = out / "last" / "training_state.pt"
    start_epoch, best_f1, history = 0, -1.0, []
    model_src = args.model
    if args.resume and state_path.exists():
        model_src = str(out / "last")
    model = AutoModelForSequenceClassification.from_pretrained(
        model_src, num_labels=len(labels), id2label=dict(enumerate(labels)), label2id=label2id
    ).to(device)

    loss_weight = None
    if args.class_weights:  # inverse-sqrt frequency, normalized to mean 1
        counts = np.bincount(y_train, minlength=len(labels)).astype(float)
        w = 1 / np.sqrt(np.maximum(counts, 1))
        loss_weight = torch.tensor(w / w.mean(), dtype=torch.float, device=device)
    loss_fn = torch.nn.CrossEntropyLoss(weight=loss_weight)

    steps_per_epoch = math.ceil(len(y_train) / args.batch_size)
    total_steps = steps_per_epoch * args.epochs
    no_decay = ("bias", "LayerNorm.weight")
    groups = [
        {"params": [p for n, p in model.named_parameters() if not any(k in n for k in no_decay)],
         "weight_decay": args.weight_decay},
        {"params": [p for n, p in model.named_parameters() if any(k in n for k in no_decay)],
         "weight_decay": 0.0},
    ]
    optimizer = torch.optim.AdamW(groups, lr=args.lr)
    scheduler = get_linear_schedule_with_warmup(optimizer, int(args.warmup * total_steps), total_steps)
    scaler = torch.amp.GradScaler("cuda", enabled=dtype == torch.float16)
    best_state = None

    if model_src != args.model:
        st = torch.load(state_path, map_location=device, weights_only=False)
        optimizer.load_state_dict(st["optimizer"])
        scheduler.load_state_dict(st["scheduler"])
        scaler.load_state_dict(st["scaler"])
        start_epoch, best_f1, history = st["epoch"] + 1, st["best_f1"], st["history"]
        if (out / "best").exists():
            best_state = AutoModelForSequenceClassification.from_pretrained(out / "best").state_dict()
        print(f"resumed after epoch {st['epoch'] + 1}; best val macro-F1 so far {best_f1:.4f}")

    lengths = [len(x) for x in enc["train"]]
    for epoch in range(start_epoch, args.epochs):
        model.train()
        batches = length_bucketed_batches(lengths, args.batch_size, seed=args.seed + epoch)
        t0, running = time.time(), 0.0
        for step, b in enumerate(batches, 1):
            batch = {k: v.to(device) for k, v in
                     collate([enc["train"][i] for i in b], [y_train[i] for i in b], pad_id).items()}
            y = batch.pop("labels")
            with torch.autocast(device.type, dtype=dtype, enabled=dtype is not None):
                logits = model(**batch).logits
            loss = loss_fn(logits.float(), y)
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            running += loss.item()
            if step % args.log_every == 0 or step == len(batches):
                rate = step / (time.time() - t0)
                eta = (len(batches) - step) / rate / 60
                print(f"epoch {epoch + 1}/{args.epochs} step {step}/{len(batches)} "
                      f"loss {running / step:.4f} | {rate:.2f} it/s | epoch ETA {eta:.1f} min",
                      flush=True)

        val_metrics, _ = evaluate(val_df, predict(model, enc["val"], args.batch_size, device,
                                                  dtype, pad_id), labels, label_col)
        history.append({"epoch": epoch + 1, "train_loss": running / len(batches),
                        "val_macro_f1": val_metrics["macro_f1"],
                        "val_accuracy": val_metrics["accuracy"],
                        "epoch_minutes": (time.time() - t0) / 60})
        print(f"epoch {epoch + 1}: val macro-F1 {val_metrics['macro_f1']:.4f} "
              f"accuracy {val_metrics['accuracy']:.4f}", flush=True)
        if val_metrics["macro_f1"] > best_f1:
            best_f1 = val_metrics["macro_f1"]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            model.save_pretrained(out / "best")
            tokenizer.save_pretrained(out / "best")
        # Checkpoint every epoch so a Colab disconnect costs at most one epoch.
        model.save_pretrained(out / "last")
        tokenizer.save_pretrained(out / "last")
        torch.save({"optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                    "scaler": scaler.state_dict(), "epoch": epoch, "best_f1": best_f1,
                    "history": history}, state_path)

    # Final evaluation with the best-on-validation weights; test is touched once.
    if best_state is not None:
        model.load_state_dict(best_state)
    results = {}
    for split, df in [("val", val_df), ("test", test_df)]:
        metrics, preds = evaluate(df, predict(model, enc[split], args.batch_size, device, dtype,
                                              pad_id), labels, label_col)
        save_reports(out, split, metrics, preds, labels, label_col)
        results[split] = {k: metrics[k] for k in ("n", "n_excluded_unseen_label", "accuracy",
                                                   "macro_f1", "weighted_f1")}

    run_info = {
        "args": vars(args), "labels": labels, "history": history, "results": results,
        "train_rows": len(train_df), "val_rows": len(val_df), "test_rows": len(test_df),
        "train_truncated_frac": float(trunc), "device": str(device), "dtype": str(dtype),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "versions": {"python": platform.python_version(), "torch": torch.__version__,
                     "transformers": transformers.__version__, "sklearn": sklearn.__version__,
                     "pandas": pd.__version__},
    }
    (out / "run_info.json").write_text(json.dumps(run_info, indent=2, default=str))
    return results
