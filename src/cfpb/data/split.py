"""Classifier splits and the stratified annotation sample."""
import pandas as pd
from sklearn.model_selection import train_test_split

from cfpb.config import PRODUCT_TO_REGULATION, RANDOM_SEED


def make_splits(df: pd.DataFrame, label_col: str = "product",
                val_frac: float = 0.1, test_frac: float = 0.1,
                max_per_class: int | None = None) -> dict[str, pd.DataFrame]:
    """Stratified train/val/test split. Expects df already deduped on
    text_hash (clean.filter_narratives) so duplicates cannot leak.

    max_per_class caps the dominant classes (credit reporting is ~90% of
    rows) to keep fine-tuning affordable; evaluation uses macro-F1 anyway.
    """
    if max_per_class:
        df = (df.sample(frac=1, random_state=RANDOM_SEED)
                .groupby(label_col).head(max_per_class))
    # Classes too small to stratify go to train only.
    counts = df[label_col].value_counts()
    rare = df[label_col].isin(counts[counts < 10].index)
    main = df[~rare]
    train, rest = train_test_split(main, test_size=val_frac + test_frac,
                                   stratify=main[label_col], random_state=RANDOM_SEED)
    val, test = train_test_split(rest, test_size=test_frac / (val_frac + test_frac),
                                 stratify=rest[label_col], random_state=RANDOM_SEED)
    train = pd.concat([train, df[rare]])
    return {"train": train.reset_index(drop=True), "val": val.reset_index(drop=True),
            "test": test.reset_index(drop=True)}


def annotation_sample(df: pd.DataFrame, per_regulation: int = 30,
                      exclude_ids: set[str] | None = None) -> pd.DataFrame:
    """Stratified sample for the gold retrieval set (~30 per regulation,
    CLAUDE.md Sec. 4-5), with empty columns for annotators to fill in.
    Pass exclude_ids (e.g. the classifier test set) to keep sets disjoint
    if the team decides they must be."""
    df = df.assign(regulation_candidate=df["product"].map(PRODUCT_TO_REGULATION))
    df = df[df["regulation_candidate"].notna()]
    if exclude_ids:
        df = df[~df["complaint_id"].isin(exclude_ids)]
    # Round-robin across products within each regulation so e.g. Reg Z is
    # not all mortgages: shuffle, rank rows within their product, take the
    # lowest ranks first.
    df = df.sample(frac=1, random_state=RANDOM_SEED)
    df = df.assign(_rank=df.groupby("product").cumcount()).sort_values("_rank", kind="stable")
    out = df.groupby("regulation_candidate").head(per_regulation).reset_index(drop=True)
    cols = ["complaint_id", "regulation_candidate", "product", "sub_product",
            "issue", "sub_issue", "company", "narrative_clean"]
    out = out[cols]
    # Filled in by annotators, per the rubric.
    for c in ["gold_regulation", "gold_section", "gold_paragraph",
              "annotator", "confidence", "notes"]:
        out[c] = ""
    return out
