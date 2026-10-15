"""Look up regulation text and annotation complaints from the command line.

Used by the regulation-annotator skill (.claude/skills/regulation-annotator)
and by human annotators. Reads data/processed/reg_chunks.parquet
(scripts/build_reg_corpus.py) and data/processed/annotation_sample.csv.

    python scripts/reg_lookup.py --section 1026.13                 # rule text
    python scripts/reg_lookup.py --section 1026.13 --interp        # + official interpretations
    python scripts/reg_lookup.py --paragraph "1026.13(a)"          # one paragraph (prefix match)
    python scripts/reg_lookup.py --search "unauthorized debit card charge" --reg E --k 8
    python scripts/reg_lookup.py --complaints 0 5                  # annotation items 0..4
    python scripts/reg_lookup.py --complaint 18240318              # one item by complaint_id
"""
import argparse
import sys
import textwrap
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import PROCESSED_DIR  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def show(rows: pd.DataFrame, width: int = 100) -> None:
    for _, r in rows.iterrows():
        print(f"\n=== {r['chunk_id']}  [{r['kind']}]  {r['heading']}")
        print(textwrap.fill(r["text"], width) if "\n" not in r["text"] else r["text"])
        print(f"--- source: {r['source_url']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section")
    ap.add_argument("--paragraph")
    ap.add_argument("--interp", action="store_true", help="include official interpretations")
    ap.add_argument("--search")
    ap.add_argument("--reg", choices=list("EFVZ"))
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--complaints", nargs=2, type=int, metavar=("START", "N"))
    ap.add_argument("--complaint")
    args = ap.parse_args()

    if args.complaints or args.complaint:
        a = pd.read_csv(PROCESSED_DIR / "annotation_sample.csv", dtype=str, keep_default_na=False)
        a = a.reset_index().rename(columns={"index": "item"})
        sel = (a[a["complaint_id"] == args.complaint] if args.complaint
               else a.iloc[args.complaints[0]:args.complaints[0] + args.complaints[1]])
        for _, r in sel.iterrows():
            # regulation_candidate is deliberately NOT shown (sampling heuristic; would bias labels)
            print(f"\n##### item {r['item']} | complaint_id {r['complaint_id']}\n"
                  f"product: {r['product']} | sub_product: {r['sub_product']}\n"
                  f"issue: {r['issue']} | sub_issue: {r['sub_issue']} | company: {r['company']}\n")
            print(textwrap.fill(r["narrative_clean"], 100))
        return

    chunks = pd.read_parquet(PROCESSED_DIR / "reg_chunks.parquet")
    kinds = ["regulation", "interpretation"] if args.interp else ["regulation"]
    if args.section:
        show(chunks[(chunks["section"] == args.section) & chunks["kind"].isin(kinds)])
    elif args.paragraph:
        show(chunks[chunks["paragraph"].str.startswith(args.paragraph) & chunks["kind"].isin(kinds)])
    elif args.search:
        from sklearn.feature_extraction.text import TfidfVectorizer
        pool = chunks[chunks["kind"].isin(kinds + (["interpretation"] if not args.interp else []))]
        if args.reg:
            pool = pool[pool["regulation"] == args.reg]
        vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, ngram_range=(1, 2))
        mat = vec.fit_transform(pool["heading"] + " " + pool["text"])
        scores = (mat @ vec.transform([args.search]).T).toarray().ravel()
        top = pool.assign(score=scores).sort_values("score", ascending=False).head(args.k)
        for _, r in top.iterrows():
            print(f"{r['score']:.3f}  {r['chunk_id']:32s} {r['heading'][:70]}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
