"""Fill the app's database with the 198 gold-set complaints.

    python -m app.backend.seed                      # default run folder (see below)
    python -m app.backend.seed --run outputs/pipeline_runs/full-bm25 --reset

Every gold complaint becomes a case (company, product, issue, state and the CFPB
filing date from data/processed/complaints.parquet). Complaints that a saved
pipeline run already drafted and checked are imported with that analysis, so
the inbox has reviewable drafts without any API call; the rest start as "new"
and are analysed live from the case page.

The saved run defaults to outputs/pipeline_runs/full-bm25 (Anirudh's full run,
Drive final-experiments/anirudh/) and falls back to pilot-bm25 (midterm pilot,
drafted by the now-retired Nemotron model). Classification and the scope check
are recomputed with the current models; the draft and its NLI scores come from
the run and are labelled at the app's cutoff.

Received dates are simulated (spread over the last 14 days) so the response
deadlines in the demo are live; the real CFPB date is kept in cfpb_date_received.
"""
import argparse
import hashlib
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import pandas as pd

from app.backend import config
from app.backend.db import Analysis, Base, Case, DraftVersion, Session, engine, init_db, log_event, now
from app.backend.engine import MODELS, chunk_dicts, draft_sentences

RUNS = config.ROOT / "outputs" / "pipeline_runs"


def default_run() -> Path:
    for name in ("full-bm25", "pilot-bm25"):
        if (RUNS / name / "responses.parquet").exists():
            return RUNS / name
    raise SystemExit("No saved run found under outputs/pipeline_runs (full-bm25 or pilot-bm25).")


def simulated_received(cid: str):
    h = int(hashlib.sha1(cid.encode()).hexdigest(), 16)
    return now() - timedelta(days=h % 14, hours=(h >> 8) % 24, minutes=(h >> 16) % 60)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=None, help="saved pipeline run folder to import drafts from")
    ap.add_argument("--reset", action="store_true", help="drop and recreate the app's tables first")
    args = ap.parse_args()
    run = args.run or default_run()

    if args.reset:
        Base.metadata.drop_all(engine)
    init_db()

    from cfpb.annotation import load_items
    from cfpb.pipeline.corpus import PAIR_B_CORPUS, REG_CORPUS, Corpus
    items = load_items()
    meta = pd.read_parquet(config.ROOT / "data" / "processed" / "complaints.parquet",
                           columns=["complaint_id", "date_received", "state", "company", "product",
                                    "sub_product", "issue", "narrative"])
    meta["complaint_id"] = meta["complaint_id"].astype(str)
    meta = meta[meta["complaint_id"].isin(set(items["complaint_id"]))].set_index("complaint_id")

    print("loading models (classifier, BM25, mpnet, scope)...")
    MODELS.load(light=True)
    if MODELS.error:
        raise SystemExit(MODELS.error)
    lookup = Corpus.merge(*[Corpus.load(p) for p in (PAIR_B_CORPUS, REG_CORPUS) if Path(p).exists()], keep_first=True)

    responses = pd.read_parquet(run / "responses.parquet")
    responses["complaint_id"] = responses["complaint_id"].astype(str)
    sentences = pd.read_parquet(run / "sentences.parquet")
    sentences["complaint_id"] = sentences["complaint_id"].astype(str)
    ranked = pd.read_parquet(run / "ranked.parquet")
    ranked["complaint_id"] = ranked["complaint_id"].astype(str)
    retriever_name = str(ranked["retriever"].iloc[0]) if "retriever" in ranked else run.name
    replay_ids = set(responses["complaint_id"])

    n_new = n_replay = 0
    with Session() as s:
        existing = {c.external_id for c in s.query(Case.external_id)}
        for row in items.itertuples():
            cid = row.complaint_id
            if cid in existing:
                continue
            m = meta.loc[cid] if cid in meta.index else None
            case = Case(external_id=cid, source="cfpb_gold",
                        narrative=(m["narrative"] if m is not None and isinstance(m["narrative"], str) else row.narrative_clean),
                        company=row.company, product=row.product, sub_product=row.sub_product, issue=row.issue,
                        state=(m["state"] if m is not None else None),
                        cfpb_date_received=(str(m["date_received"])[:10] if m is not None else None),
                        received_at=simulated_received(cid), status="new")
            s.add(case)
            s.flush()
            log_event(s, case, "system", "imported", f"CFPB complaint {cid}, filed {case.cfpb_date_received}.")

            if cid in replay_ids:
                r = responses[responses["complaint_id"] == cid].iloc[0]
                g = ranked[ranked["complaint_id"] == cid].sort_values("rank").head(5)
                chunks = [lookup.get(str(c)).ranked(i + 1, float(sc)) for i, (c, sc) in enumerate(zip(g["chunk_id"], g["score"]))]
                clean = row.narrative_clean
                sc_rows = sentences[sentences["complaint_id"] == cid].sort_values("sentence_idx")
                ens = len(sc_rows) and str(sc_rows["verifier"].iloc[0]).startswith("mean(")
                cut = config.ENSEMBLE_CUTOFF if ens else config.NLI_CUTOFF  # a replayed run keeps its own checker
                checks = [{"sentence_idx": int(x.sentence_idx), "sentence": x.sentence,
                           "premise_chunk_ids": list(x.premise_chunk_ids), "entail_prob": float(x.entail_prob),
                           "contradict_prob": float(x.contradict_prob),
                           "label": "supported" if x.entail_prob >= cut else "unsupported"}
                          for x in sc_rows.itertuples()]
                sents, cited = list(r["sentences"]), [list(c) for c in r["cited_chunk_ids"]]
                a = Analysis(case_id=case.id, origin=f"replay:{run.name}", stage="done", narrative_clean=clean,
                             classification=asdict(MODELS.classifier.classify(clean)),
                             retrieval={"retriever": retriever_name, "corpus": lookup.name, "chunks": chunk_dicts(chunks)},
                             scope=MODELS.scope_for(clean),
                             draft={"response": r["response"], "sentences": sents, "cited_chunk_ids": cited,
                                    "context_chunk_ids": list(r["context_chunk_ids"]), "model": r["model"],
                                    "prompt_version": r["prompt_version"], "is_referral": bool(r["is_referral"])},
                             checks=checks, generator_model=str(r["model"]),
                             verifier=str(sc_rows["verifier"].iloc[0]) if len(sc_rows) else None,
                             nli_cutoff=cut, timings_ms={}, finished_at=now())
                s.add(a)
                s.flush()
                s.add(DraftVersion(case_id=case.id, analysis_id=a.id, version=1, author="AI draft",
                                   sentences=draft_sentences(sents, cited, checks)))
                case.status = "in_review"
                n_flag = sum(c["label"] == "unsupported" for c in checks)
                log_event(s, case, "system", "analysis_done",
                          f"Imported from saved run {run.name} (drafted by {r['model']}): "
                          f"{len(sents)} sentences, {n_flag} flagged.")
                n_replay += 1
            else:
                n_new += 1
        s.commit()
    print(f"seeded {n_replay} analysed cases from {run.name} and {n_new} new cases "
          f"({len(existing)} already present) into {'Postgres schema ' + config.SCHEMA if config.DATABASE_URL.startswith('postgres') else config.DATABASE_URL}")


if __name__ == "__main__":
    main()
