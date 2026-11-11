"""Tokenization and batching for the DistilBERT complaint classifier."""
import random

import pandas as pd
import torch

TEXT_COL = "narrative_clean"


def load_split(path, label_col: str, max_rows: int | None = None, seed: int = 544) -> pd.DataFrame:
    df = pd.read_parquet(path, columns=["complaint_id", TEXT_COL, label_col])
    df = df.dropna(subset=[TEXT_COL, label_col])
    if max_rows and len(df) > max_rows:
        df = df.sample(max_rows, random_state=seed)
    return df.reset_index(drop=True)


def encode(texts, tokenizer, max_len: int = 512, head: int = 128) -> list[list[int]]:
    """Tokenize and fit each text into max_len tokens.

    Long narratives keep their first `head` tokens and their last
    (max_len - specials - head) tokens. Head+tail truncation worked best for
    long documents in Sun et al. 2019, "How to Fine-Tune BERT for Text
    Classification?". Complaints often state the facts first and the request
    at the end. head >= max_len means plain head-only truncation.
    """
    # Add [CLS] ... [SEP] by hand: build_inputs_with_special_tokens was removed
    # in transformers 5, and Colab may have either major version.
    start, end = tokenizer.cls_token_id, tokenizer.sep_token_id
    if start is None or end is None:
        raise ValueError("encode() expects a BERT-style tokenizer with [CLS] and [SEP]")
    budget = max_len - 2
    ids_list = tokenizer(list(texts), add_special_tokens=False, truncation=False)["input_ids"]
    out = []
    for ids in ids_list:
        if len(ids) > budget:
            ids = ids[:budget] if head >= budget else ids[:head] + ids[len(ids) - (budget - head):]
        out.append([start] + ids + [end])
    return out


def length_bucketed_batches(lengths: list[int], batch_size: int, seed: int,
                            shuffle: bool = True) -> list[list[int]]:
    """Group similar-length examples into batches to cut padding (median
    narrative is ~175 words, so padding everything to 512 wastes most compute).
    Shuffles within large pools and then shuffles batch order, so training
    still sees a random mix of lengths across steps."""
    idx = list(range(len(lengths)))
    rng = random.Random(seed)
    if shuffle:
        rng.shuffle(idx)
    pool = batch_size * 50
    batches = []
    for start in range(0, len(idx), pool):
        chunk = sorted(idx[start:start + pool], key=lambda i: lengths[i])
        batches += [chunk[i:i + batch_size] for i in range(0, len(chunk), batch_size)]
    if shuffle:
        rng.shuffle(batches)
    return batches


def collate(batch_ids: list[list[int]], labels: list[int] | None, pad_id: int) -> dict:
    width = max(len(x) for x in batch_ids)
    input_ids = torch.full((len(batch_ids), width), pad_id, dtype=torch.long)
    mask = torch.zeros((len(batch_ids), width), dtype=torch.long)
    for i, ids in enumerate(batch_ids):
        input_ids[i, :len(ids)] = torch.tensor(ids)
        mask[i, :len(ids)] = 1
    out = {"input_ids": input_ids, "attention_mask": mask}
    if labels is not None:
        out["labels"] = torch.tensor(labels, dtype=torch.long)
    return out
