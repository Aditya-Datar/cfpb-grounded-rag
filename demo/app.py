"""Minimal Streamlit demo over cfpb.pipeline (skeleton for the demo owner).

    streamlit run demo/app.py

Shows each stage's output for one complaint. Stages that are not built yet
run as stubs and are labelled on the page. With the oracle retriever, pick a
gold-set complaint to see its gold regulation section (real eCFR / U.S. Code
text); this needs data/processed/reg_chunks.parquet
(scripts/build_reg_corpus.py --date 2026-10-13) and annotation_sample.csv.
"""
import html
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.pipeline import load_pipeline  # noqa: E402
from cfpb.pipeline.corpus import DEFAULT_CORPUS, Corpus, OracleRetriever, load_gold  # noqa: E402
from cfpb.pipeline.schema import SUPPORTED, UNSUPPORTED  # noqa: E402
from cfpb.pipeline.stages import citation  # noqa: E402

st.set_page_config(page_title="CFPB Complaint Triage", layout="wide")

LABEL_STYLE = {SUPPORTED: ("rgba(46,160,67,0.18)", "supported"),
               UNSUPPORTED: ("rgba(218,54,51,0.20)", "flagged")}
UNCHECKED_STYLE = ("rgba(128,128,128,0.15)", "not checked")


@st.cache_resource(show_spinner="Loading models...")
def get_pipeline():
    return load_pipeline()


@st.cache_resource(show_spinner="Loading regulation corpus...")
def get_oracle():
    return OracleRetriever(Corpus.load(DEFAULT_CORPUS), load_gold())


@st.cache_data
def gold_examples() -> dict[str, tuple[str, str]]:
    """complaint_id -> (label for the picker, narrative) for gold items with text."""
    from cfpb.annotation import load_items
    try:
        items = load_items()
    except FileNotFoundError:
        return {}
    gold = load_gold()
    out = {}
    for row in items.itertuples():
        g = gold.get(row.complaint_id)
        if g:
            target = g["gold_paragraph"] or g["gold_section"] or "NONE"
            out[row.complaint_id] = (f"{row.complaint_id} · {row.product[:40]} · gold {target}",
                                     row.narrative_clean)
    return out


def stub_note(stage: str, stubbed: list[str]) -> None:
    if stage in stubbed:
        st.caption(":orange-badge[Placeholder] This stage is not built yet; output is a stub.")


st.title("CFPB complaint triage")
st.caption("Drafts for a compliance officer to review. Not legal advice; every draft needs human review.")

pipe = get_pipeline()

with st.sidebar:
    st.header("Settings")
    oracle_ok = DEFAULT_CORPUS.exists()
    mode = st.radio("Retriever", ["Default", "Oracle (gold section)"],
                    help="Oracle returns the hand-labelled section for a gold-set complaint.",
                    disabled=not oracle_ok)
    if not oracle_ok:
        st.caption("Oracle needs data/processed/reg_chunks.parquet.")
    k = st.slider("Chunks to retrieve (k)", 1, 10, 5)
    examples = gold_examples()
    complaint_id = None
    if examples:
        complaint_id = st.selectbox("Gold-set complaint", [None, *examples],
                                    format_func=lambda c: "Type your own" if c is None else examples[c][0])
    elif mode.startswith("Oracle"):
        st.warning("No gold-set complaint text found (data/processed/annotation_sample.csv).")

default_text = examples[complaint_id][1] if complaint_id else ""
text = st.text_area("Complaint narrative", value=default_text, height=200,
                    key=f"text-{complaint_id}")
use_oracle = mode.startswith("Oracle")
if use_oracle and not complaint_id:
    st.info("Pick a gold-set complaint in the sidebar to use the oracle retriever.")

if st.button("Analyze", type="primary", disabled=not text.strip() or (use_oracle and not complaint_id)):
    retriever = get_oracle().for_complaint(complaint_id) if use_oracle else None
    result = pipe.analyze(text, k=k, retriever=retriever)
    stubbed = result.stubbed_stages

    st.subheader("1. Classification")
    stub_note("classify", stubbed)
    c = result.classification
    rows = [f"**Product:** {c.product.label} (confidence {c.product.prob:.2f})"]
    if c.issue:
        rows.append(f"**Issue:** {c.issue.label} (confidence {c.issue.prob:.2f})")
    rows.append(f"**Candidate regulation (from product):** {c.candidate_regulation or 'none'}")
    st.markdown("  \n".join(rows))

    st.subheader("2. Governing regulation")
    stub_note("retrieve", stubbed)
    r = result.retrieval
    st.caption(f"Retriever: {r.retriever} · corpus: {r.corpus}")
    if r.abstained:
        st.warning("No in-scope section found: the complaint is outside Regulations E, F, V, Z "
                   "and the FCRA, so it is referred to compliance.")
    for ch in r.chunks:
        with st.expander(f"#{ch.rank} {citation(ch)} · score {ch.score:.2f}", expanded=ch.rank == 1):
            st.markdown(f"**{ch.heading}**")
            st.text(ch.text)
            st.markdown(f"[Source]({ch.source_url})")

    st.subheader("3. Draft response" if not result.draft.is_referral else "3. Referral")
    stub_note("generate", stubbed)
    checks = {s.sentence_idx: s for s in result.verification.checks}
    spans = []
    for i, sent in enumerate(result.draft.sentences):
        check = checks.get(i)
        color, tag = LABEL_STYLE.get(check.label, UNCHECKED_STYLE) if check else UNCHECKED_STYLE
        spans.append(f'<span title="{tag}" style="background:{color};padding:2px 4px;'
                     f'border-radius:4px;line-height:1.9">{html.escape(sent)}</span>')
    st.markdown(" ".join(spans), unsafe_allow_html=True)

    st.subheader("4. Sentence check")
    stub_note("verify", stubbed)
    v = result.verification
    if not v.checks:
        st.caption("Not run for referrals.")
    else:
        cols = st.columns(3)
        cols[0].metric("Sentences", len(v.checks))
        cols[1].metric("Supported", v.n_supported)
        cols[2].metric("Flagged for review", v.n_flagged)
        st.dataframe([{"#": s.sentence_idx + 1, "sentence": s.sentence, "label": s.label,
                       "entailment": s.entail_prob, "checked against": ", ".join(s.premise_chunk_ids)}
                      for s in v.checks], hide_index=True)

    if complaint_id:
        g = load_gold()[complaint_id]
        st.caption(f"Gold label: {g['gold_regulation']} {g['gold_paragraph'] or g['gold_section'] or ''}")
    st.caption("Stage timings (ms): " + ", ".join(f"{k} {v:.0f}" for k, v in result.timings_ms.items()))
