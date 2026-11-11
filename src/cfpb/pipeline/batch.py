"""Turn many PipelineResults into the stage Parquet tables of docs/INTERFACES.md.

Used by scripts/run_pipeline_batch.py so the demo and the evaluation share one
code path. Metrics are not computed here; the shared evaluation script reads
these tables.
"""
import pandas as pd

from cfpb.pipeline.schema import PipelineResult


def to_frames(results: dict[str, PipelineResult], condition: str) -> dict[str, pd.DataFrame]:
    """complaint_id -> result, to {classification, ranked, responses, sentences}.
    `condition` is "retrieved" or "oracle" (INTERFACES.md Sec. 4)."""
    cls, ranked, responses, sentences = [], [], [], []
    for cid, r in results.items():
        c = r.classification
        cls.append(dict(complaint_id=cid, pred_product=c.product.label,
                        pred_product_prob=c.product.prob,
                        pred_issue=c.issue.label if c.issue else None,
                        pred_issue_prob=c.issue.prob if c.issue else None,
                        candidate_regulation=c.candidate_regulation, classifier=c.source))
        ret = r.retrieval
        ranked += [dict(complaint_id=cid, retriever=ret.retriever, corpus=ret.corpus, rank=ch.rank,
                        chunk_id=ch.chunk_id, score=ch.score, section=ch.section,
                        abstain_score=ret.abstain_score, abstained=ret.abstained)
                   for ch in ret.chunks]
        if not ret.chunks:  # keep abstentions visible as one row with no chunk
            ranked.append(dict(complaint_id=cid, retriever=ret.retriever, corpus=ret.corpus,
                               rank=None, chunk_id=None, score=None, section=None,
                               abstain_score=ret.abstain_score, abstained=ret.abstained))
        d = r.draft
        responses.append(dict(complaint_id=cid, condition=condition,
                              context_chunk_ids=d.context_chunk_ids, model=d.model,
                              prompt_version=d.prompt_version, response=d.response,
                              sentences=d.sentences, cited_chunk_ids=d.cited_chunk_ids,
                              is_referral=d.is_referral))
        v = r.verification
        sentences += [dict(complaint_id=cid, condition=condition, sentence_idx=s.sentence_idx,
                           sentence=s.sentence, premise_chunk_ids=s.premise_chunk_ids,
                           entail_prob=s.entail_prob, contradict_prob=s.contradict_prob,
                           label=s.label, verifier=v.verifier, threshold=v.threshold)
                      for s in v.checks]
    return {"classification": pd.DataFrame(cls), "ranked": pd.DataFrame(ranked),
            "responses": pd.DataFrame(responses), "sentences": pd.DataFrame(sentences)}
