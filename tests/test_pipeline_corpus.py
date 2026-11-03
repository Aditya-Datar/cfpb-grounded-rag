import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.pipeline import Pipeline  # noqa: E402
from cfpb.pipeline.core import DEFAULT_PRODUCT_MODEL, load_pipeline  # noqa: E402
from cfpb.pipeline import corpus as corpus_mod  # noqa: E402
from cfpb.pipeline.corpus import Corpus, OracleRetriever, default_corpus_path, load_gold  # noqa: E402
from cfpb.pipeline.stages import StubClassifier, StubGenerator, StubRetriever, StubVerifier  # noqa: E402

REG_ROWS = [  # regulation-corpus format (reg_chunks.parquet)
    dict(chunk_id="R:1005.11(a)", regulation="E", part="1005", kind="regulation", section="1005.11",
         paragraph="1005.11(a)", heading="§ 1005.11", text="(a) Definition of error.", n_words=4,
         source_url="u"),
    dict(chunk_id="R:1005.11(c)", regulation="E", part="1005", kind="regulation", section="1005.11",
         paragraph="1005.11(c)", heading="§ 1005.11", text="(c) Time limits.", n_words=3, source_url="u"),
    dict(chunk_id="I:1005.11(c)~1", regulation="E", part="1005", kind="interpretation",
         section="1005.11", paragraph="1005.11(c)", heading="§ 1005.11", text="Comment.", n_words=1,
         source_url="u"),
    dict(chunk_id="S:1681i(a)(1)", regulation="FCRA", part="1681", kind="statute", section="1681i",
         paragraph="1681i(a)(1)", heading="§ 1681i", text="(1) Reinvestigation.", n_words=2,
         source_url="u"),
]
CHUNKING_ROWS = [  # chunking-branch format (chunks.jsonl)
    dict(chunk_id="12-1005-1005.11-c-2", part="1005", section="1005.11", paragraph="(c)(2)",
         heading="Procedures", text="(c)(2) Ten business days.", source_url="u", embed_text="x",
         content_type="regulation", regulation="E", path_certain=True, n_chars=10, record_id="r"),
    dict(chunk_id="12-1005-1005.1-all", part="1005", section="1005.1", paragraph="",
         heading="Authority", text="Whole section.", source_url="u", embed_text="x",
         content_type="regulation", regulation="E", path_certain=True, n_chars=10, record_id="r"),
]
GOLD = {
    "1": dict(complaint_id="1", gold_regulation="E", gold_section="1005.11", gold_paragraph="1005.11(c)(1)"),
    "2": dict(complaint_id="2", gold_regulation="NONE", gold_section=None, gold_paragraph=None),
    "3": dict(complaint_id="3", gold_regulation="FCRA", gold_section="1681i", gold_paragraph="1681i(a)"),
}


@pytest.fixture
def reg_corpus(tmp_path):
    path = tmp_path / "reg_chunks.parquet"
    pd.DataFrame(REG_ROWS).to_parquet(path)
    return Corpus.load(path)


def test_load_both_formats_to_one_shape(reg_corpus, tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in CHUNKING_ROWS), encoding="utf-8")
    chunking = Corpus.load(path)
    assert chunking.get("12-1005-1005.11-c-2").paragraph == "1005.11(c)(2)"  # made full-form
    assert chunking.get("12-1005-1005.1-all").paragraph == ""
    assert chunking.kinds == ["regulation"]
    assert reg_corpus.get("R:1005.11(c)").paragraph == "1005.11(c)"
    assert reg_corpus.kinds == ["interpretation", "regulation", "statute"]


def test_missing_corpus_explains_how_to_build(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_reg_corpus"):
        Corpus.load(tmp_path / "nope.parquet")


def test_section_excludes_interpretations_by_default(reg_corpus):
    assert [c.chunk_id for c in reg_corpus.section("1005.11")] == ["R:1005.11(a)", "R:1005.11(c)"]
    assert len(reg_corpus.section("1005.11", kinds=None)) == 3


def test_oracle_ranks_gold_paragraph_first(reg_corpus):
    r = OracleRetriever(reg_corpus, GOLD).for_complaint("1").retrieve("text", k=5)
    assert [(c.chunk_id, c.score) for c in r.chunks] == [("R:1005.11(c)", 1.0), ("R:1005.11(a)", 0.5)]
    assert [c.rank for c in r.chunks] == [1, 2]
    assert not r.abstained and r.retriever == "oracle"


def test_oracle_respects_k_and_parent_paragraph_match(reg_corpus):
    o = OracleRetriever(reg_corpus, GOLD)
    assert len(o.for_complaint("1").retrieve("t", k=1).chunks) == 1
    # gold 1681i(a) contains the 1681i(a)(1) chunk
    assert o.for_complaint("3").retrieve("t", k=5).chunks[0].score == 1.0


def test_oracle_abstains_on_none_and_rejects_unknown(reg_corpus):
    o = OracleRetriever(reg_corpus, GOLD)
    r = o.for_complaint("2").retrieve("t", k=5)
    assert r.abstained and r.chunks == []
    with pytest.raises(KeyError):
        o.for_complaint("999")


def test_oracle_missing_section_raises(tmp_path):
    path = tmp_path / "c.parquet"
    pd.DataFrame(REG_ROWS[:1]).to_parquet(path)
    with pytest.raises(LookupError):
        OracleRetriever(Corpus.load(path), GOLD).for_complaint("3").retrieve("t", 5)


def test_retriever_override_is_per_call(reg_corpus):
    pipe = Pipeline(StubClassifier(), StubRetriever(), StubGenerator(), StubVerifier())
    r = pipe.analyze("my bank ignored my error notice",
                     retriever=OracleRetriever(reg_corpus, GOLD).for_complaint("1"))
    assert r.retrieval.retriever == "oracle"
    assert "retrieve" not in r.stubbed_stages
    assert "12 CFR 1005.11(c)" in r.draft.response
    assert pipe.analyze("again").retrieval.retriever == "stub"  # default unchanged



def test_default_corpus_prefers_pair_b_then_falls_back(tmp_path, monkeypatch):
    pair_b, reg = tmp_path / "chunks.jsonl", tmp_path / "reg_chunks.parquet"
    monkeypatch.setattr(corpus_mod, "CORPUS_PREFERENCE", [pair_b, reg])
    assert default_corpus_path() == pair_b          # neither exists: names the default
    with pytest.raises(FileNotFoundError, match="chunks.jsonl"):
        Corpus.load()
    pd.DataFrame(REG_ROWS).to_parquet(reg)
    assert default_corpus_path() == reg             # fallback
    assert Corpus.load().name == "reg_chunks.parquet"
    pair_b.write_text("\n".join(json.dumps(r) for r in CHUNKING_ROWS), encoding="utf-8")
    assert default_corpus_path() == pair_b          # Pair B wins once present
    assert Corpus.load().name == "chunks.jsonl"

# --- real files: skipped unless present locally ---------------------------

@pytest.mark.skipif(not default_corpus_path().exists(), reason="no corpus file present locally")
def test_oracle_covers_every_in_scope_gold_item():
    oracle = OracleRetriever(Corpus.load())
    for gold in load_gold().values():
        r = oracle.retrieve_for(gold, k=100)
        if gold["gold_regulation"] == "NONE":
            assert r.abstained
        else:
            assert r.chunks and r.chunks[0].score == 1.0, gold["complaint_id"]


@pytest.mark.skipif(not DEFAULT_PRODUCT_MODEL.is_dir(), reason="classifier weights not present")
def test_real_classifier_through_pipeline():
    pytest.importorskip("torch")
    r = load_pipeline(require_models=True).analyze(
        "A debt collector keeps calling me about a debt I do not owe and never sent a validation notice.")
    assert "classify" not in r.stubbed_stages
    assert r.classification.product.label == "Debt collection"
    assert isinstance(r.classification.product.prob, float)
    json.dumps(r.to_dict())
