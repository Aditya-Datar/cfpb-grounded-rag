"""Minimal Streamlit demo over cfpb.pipeline (skeleton for the demo owner).

    streamlit run demo/app.py

Shows each stage's output for one complaint. Stages that are not built yet
run as stubs and are labelled on the page. With the oracle retriever, pick a
gold-set complaint to see its gold regulation section (real eCFR / U.S. Code
text); this needs a corpus (Pair B's chunking/data/processed/chunks.jsonl,
else data/processed/reg_chunks.parquet) and annotation_sample.csv.
"Precomputed rankings" replays a ranked.parquet found under
outputs/retrieval/*/ or outputs/pipeline_runs/*/ (e.g. Pair B's BM25 run).
"Default" uses the live retriever (RETRIEVER_KIND below) over Pair B's
chunks.jsonl, else a stub. For a gold-set complaint, "Compare with oracle"
shows that retriever and the gold section side by side.
"Full runs" replays the saved attribution runs (outputs/pipeline_runs/full-*,
from Drive final-experiments/anirudh/): real Nemotron drafts and NLI labels for
every gold complaint, retrieved vs oracle, with no API call or NLI model.

Free-text input uses the stub generator and verifier unless NVIDIA_API_KEY is
set in .streamlit/secrets.toml (git-ignored); then it drafts with Nemotron
(GENERATOR_MODEL in secrets.toml overrides the model) and checks with the NLI
model, which is slow on a CPU.
"""
import html
import json
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cfpb.pipeline import load_pipeline  # noqa: E402
from cfpb.config import OUTPUT_DIR, PROCESSED_DIR, ROOT  # noqa: E402
from cfpb.pipeline.corpus import (PAIR_B_CORPUS, REG_CORPUS, Corpus, OracleRetriever,  # noqa: E402
                                  default_corpus_path, load_gold)
from cfpb.pipeline.retrievers import PrecomputedRetriever  # noqa: E402
from cfpb.pipeline.schema import SUPPORTED, UNSUPPORTED  # noqa: E402
from cfpb.pipeline.stages import StubRetriever, citation  # noqa: E402
from replay import ORACLE_RUN, ReplayRun, full_runs  # noqa: E402

st.set_page_config(page_title="CFPB Complaint Triage", layout="wide")

# Live retriever for "Default" mode. Set to the winner of H1 once Ishani reports it
# (e.g. "hybrid" with its tuned alpha); "bm25" ignores alpha.
RETRIEVER_KIND, ALPHA = "bm25", 0.5
# NLI cutoffs offered in "Full runs": the run threshold, and Atharva's cutoff frozen
# on checker set 1 (docs/tasks/results/atharva.md).
FROZEN_CUTOFF = 0.99658203125
RUNS_DIR = OUTPUT_DIR / "pipeline_runs"

LABEL_STYLE = {SUPPORTED: ("rgba(46,160,67,0.18)", "supported"),
               UNSUPPORTED: ("rgba(218,54,51,0.20)", "flagged")}
UNCHECKED_STYLE = ("rgba(128,128,128,0.15)", "not checked")
# Every chunk file that may be present locally; precomputed rankings may use
# ids from any of them (Pair B's chunks.jsonl, reg_chunks.parquet).
CHUNK_FILES = [PAIR_B_CORPUS, REG_CORPUS, PROCESSED_DIR / "chunks_chunking.jsonl"]
METRICS_FILE = ROOT / "results" / "classifier_test_metrics.json"
MODES = ["Default", "Oracle (gold section)", "Precomputed rankings", "Full runs (saved drafts)"]


def secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)
    except Exception:  # no .streamlit/secrets.toml (the exception type varies by Streamlit version)
        return None


@st.cache_resource(show_spinner="Loading models...")
def get_pipeline():
    generator = verifier = None
    if key := secret("NVIDIA_API_KEY"):
        from cfpb.generate.nemotron import NemotronGenerator
        from cfpb.verify.nli import NLIVerifier
        os.environ["NVIDIA_API_KEY"] = key
        model = secret("GENERATOR_MODEL")
        generator = NemotronGenerator(model=model) if model else NemotronGenerator()
        verifier = NLIVerifier()
    return load_pipeline(generator=generator, verifier=verifier,
                         retriever_kind=RETRIEVER_KIND, alpha=ALPHA)


@st.cache_resource(show_spinner="Loading saved run...")
def get_replay(name: str) -> ReplayRun:
    return ReplayRun(RUNS_DIR / name, get_lookup_corpus())


@st.cache_resource(show_spinner="Loading regulation corpus...")
def get_oracle():
    return OracleRetriever(Corpus.load(), load_gold())  # Pair B's corpus, else reg_chunks.parquet


@st.cache_resource(show_spinner="Loading chunk files...")
def get_lookup_corpus() -> Corpus:
    return Corpus.merge(*[Corpus.load(p) for p in CHUNK_FILES if p.exists()], keep_first=True)


@st.cache_resource(show_spinner="Loading rankings...")
def get_precomputed(path: str) -> PrecomputedRetriever:
    return PrecomputedRetriever(path, get_lookup_corpus())


def ranked_files() -> list[str]:
    found = [*OUTPUT_DIR.glob("retrieval/*/ranked.parquet"), *OUTPUT_DIR.glob("pipeline_runs/*/ranked.parquet")]
    return [str(p.relative_to(ROOT)) for p in sorted(found)]


@st.cache_data
def classifier_test_metrics() -> str | None:
    """One line from results/classifier_test_metrics.json, following the team's
    reporting rule: the all-issue macro-F1 is always shown next to the
    frequent-issue (>=100 test examples) number."""
    if not METRICS_FILE.exists():
        return None
    m = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    p, i = m["product"], m["issue"]
    by = i["macro_f1_by_min_support"]
    return (f"Classifier test set (n = {p['n']:,}): product macro-F1 {p['macro_f1']:.3f}, "
            f"accuracy {p['accuracy']:.3f}. Issue macro-F1 {by['min_test_support_1']['macro_f1']:.3f} "
            f"over all {by['min_test_support_1']['n_issues']} issues, "
            f"{by['min_test_support_100']['macro_f1']:.3f} over the "
            f"{by['min_test_support_100']['n_issues']} issues with at least 100 test examples; "
            f"accuracy {i['accuracy']:.3f}; issue valid for the product {i['product_consistent_rate']:.1%}.")


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


def gold_rank(retrieval, gold_section: str | None) -> int | None:
    """Rank of the first chunk from the gold section, or None."""
    return next((c.rank for c in retrieval.chunks if gold_section and c.section == gold_section), None)


def render_retrieval(result, gold: dict | None) -> None:
    r = result.retrieval
    stub_note("retrieve", result.stubbed_stages)
    st.caption(f"Retriever: {r.retriever} · corpus: {r.corpus}")
    gold_section = gold["gold_section"] if gold else None
    if gold:
        if gold["gold_regulation"] == "NONE":
            st.caption("Gold label: NONE (no governing section). "
                       + ("The retriever abstained." if r.abstained else "The retriever did not abstain."))
        elif (rank := gold_rank(r, gold_section)):
            st.success(f"Gold section {gold_section} found at rank {rank}.")
        else:
            st.error(f"Gold section {gold_section} not in the top {len(r.chunks)}.")
    if r.abstained:
        st.warning("No in-scope section found: the complaint is outside Regulations E, F, V, Z "
                   "and the FCRA, so it is referred to compliance.")
        if r.chunks:
            st.caption("The ranked chunks below scored under the abstention threshold; shown for reference.")
    for ch in r.chunks:
        mark = " · ✓ gold section" if gold_section and ch.section == gold_section else ""
        with st.expander(f"#{ch.rank} {citation(ch)} · score {ch.score:.2f}{mark}", expanded=ch.rank == 1):
            st.markdown(f"**{ch.heading}**")
            st.text(ch.text)
            st.markdown(f"[Source]({ch.source_url})")


def render_draft(result) -> None:
    stub_note("generate", result.stubbed_stages)
    checks = {s.sentence_idx: s for s in result.verification.checks}
    spans = []
    for i, sent in enumerate(result.draft.sentences):
        check = checks.get(i)
        color, tag = LABEL_STYLE.get(check.label, UNCHECKED_STYLE) if check else UNCHECKED_STYLE
        spans.append(f'<span title="{tag}" style="background:{color};padding:2px 4px;'
                     f'border-radius:4px;line-height:1.9">{html.escape(sent)}</span>')
    st.markdown(" ".join(spans), unsafe_allow_html=True)


def render_checks(result, table: bool = True) -> None:
    stub_note("verify", result.stubbed_stages)
    v = result.verification
    if not v.checks:
        st.caption("Not run for referrals.")
        return
    cols = st.columns(3)
    cols[0].metric("Sentences", len(v.checks))
    cols[1].metric("Supported", v.n_supported)
    cols[2].metric("Flagged", v.n_flagged)
    if table:
        st.dataframe([{"#": s.sentence_idx + 1, "sentence": s.sentence, "label": s.label,
                       "entailment": s.entail_prob, "checked against": ", ".join(s.premise_chunk_ids)}
                      for s in v.checks], hide_index=True)


st.title("CFPB complaint triage")
st.info("**For compliance staff, not legal advice.** This tool drafts a response for a compliance "
        "officer to review: it names the regulation section it relied on and flags sentences the "
        "cited text may not support. A person must check every draft before anything is sent.")

pipe = get_pipeline()

with st.sidebar:
    st.header("Settings")
    oracle_ok, rankings = default_corpus_path().exists(), ranked_files()
    runs = full_runs(RUNS_DIR) if (RUNS_DIR / ORACLE_RUN).is_dir() else []
    available = [m for m in MODES if m == "Default" or (m == MODES[1] and oracle_ok)
                 or (m == MODES[2] and rankings) or (m == MODES[3] and runs)]
    mode = st.radio("Retriever", available,
                    help="Oracle returns the hand-labelled section for a gold-set complaint. "
                         "Precomputed replays a saved ranking for a gold-set complaint. "
                         "Full runs replays the saved drafts and sentence checks of the "
                         "attribution experiment, retrieved vs oracle.")
    if not oracle_ok:
        st.caption("Oracle needs chunking/data/processed/chunks.jsonl or data/processed/reg_chunks.parquet.")
    if not runs:
        st.caption("Full runs needs outputs/pipeline_runs/full-oracle-nli and a full-<retriever> folder "
                   "(Drive final-experiments/anirudh/).")
    precomputed = replay = oracle_replay = None
    cutoff = None
    if mode == MODES[2]:
        precomputed = get_precomputed(st.selectbox("Rankings file", rankings))
    if mode == MODES[3]:
        replay = get_replay(st.selectbox("Retrieved run", runs))
        oracle_replay = get_replay(ORACLE_RUN)
        cutoffs = {f"{replay.run_threshold:g} (run threshold)": replay.run_threshold,
                   f"{FROZEN_CUTOFF:.4f} (frozen on checker set 1)": FROZEN_CUTOFF}
        cutoff = cutoffs[st.radio("NLI cutoff", list(cutoffs),
                                  help="A sentence is supported if its entailment score is at least "
                                       "the cutoff. Scores are stored, so changing it reruns nothing.")]
        st.caption(f"Drafted by {replay.model}; checked by {replay.verifier.removeprefix('nli:')}.")
    k = st.slider("Chunks to retrieve (k)", 1, 10, 5, disabled=mode == MODES[3],
                  help="Full runs always show the k = 5 the drafts were written from.")
    if mode == MODES[3]:
        k = 5
    examples = gold_examples()
    restrict = (precomputed.complaint_ids if precomputed
                else replay.complaint_ids & oracle_replay.complaint_ids if replay else None)
    if restrict is not None:
        examples = {cid: v for cid, v in examples.items() if cid in set(restrict)}
    complaint_id = None
    if examples:
        options = list(examples) if replay else [None, *examples]
        complaint_id = st.selectbox("Gold-set complaint", options,
                                    format_func=lambda c: "Type your own" if c is None else examples[c][0])
    elif mode != "Default":
        st.warning("No gold-set complaint text found for this mode (data/processed/annotation_sample.csv).")
    compare = bool(replay)
    if complaint_id and mode in (MODES[0], MODES[2]) and oracle_ok:
        compare = st.toggle("Compare with oracle (gold section)",
                            help="Runs the complaint twice, with this retriever and with the gold "
                                 "section, side by side: the attribution experiment for one complaint.")

default_text = examples[complaint_id][1] if complaint_id else ""
text = st.text_area("Complaint narrative", value=default_text, height=200,
                    key=f"text-{complaint_id}", disabled=bool(replay),
                    help="Full runs show the saved drafts for this exact text." if replay else None)
needs_id = mode != "Default"
if needs_id and not complaint_id:
    st.info(f"Pick a gold-set complaint in the sidebar to use the {mode.lower()} retriever.")

if st.button("Analyze", type="primary", disabled=not text.strip() or (needs_id and not complaint_id)):
    retriever = None
    if mode == MODES[1]:
        retriever = get_oracle().for_complaint(complaint_id)
    elif mode == MODES[2]:
        retriever = precomputed.for_complaint(complaint_id)
    if replay:
        # Classify live; an abstaining stub retriever skips drafting and checking,
        # which come from the saved runs instead.
        base = pipe.analyze(text, k=k, retriever=StubRetriever(abstain=True))
        result = replay.result(base, complaint_id, k, cutoff)
        oracle_result = oracle_replay.result(base, complaint_id, k, cutoff)
    else:
        result = pipe.analyze(text, k=k, retriever=retriever)
        oracle_result = (pipe.analyze(text, k=k, retriever=get_oracle().for_complaint(complaint_id))
                         if compare else None)
    gold = load_gold()[complaint_id] if complaint_id else None

    st.subheader("1. Classification")
    stub_note("classify", result.stubbed_stages)
    c = result.classification
    rows = [f"**Product:** {c.product.label} (confidence {c.product.prob:.2f})"]
    if c.issue:
        rows.append(f"**Issue:** {c.issue.label} (confidence {c.issue.prob:.2f})")
    rows.append(f"**Candidate regulation (from product):** {c.candidate_regulation or 'none'}")
    st.markdown("  \n".join(rows))
    if "classify" not in result.stubbed_stages and (metrics := classifier_test_metrics()):
        st.caption(metrics)

    if oracle_result:
        st.caption("Same complaint, two passages: what the retriever found (left) and the hand-labelled "
                   "gold section (right). With real drafting and checking, the difference between the "
                   "two drafts is the error caused by retrieval; what remains on the right is generation "
                   "error (the attribution experiment)."
                   + (f" Saved drafts and NLI scores from the full runs, labelled at cutoff {cutoff:g}."
                      if replay else ""))
        panes = [(f"Retrieved ({result.retrieval.retriever})", result), ("Oracle (gold section)", oracle_result)]
        st.subheader("2. Governing regulation")
        for col, (title, res) in zip(st.columns(2), panes):
            with col:
                st.markdown(f"**{title}**")
                render_retrieval(res, gold)
        st.subheader("3. Draft response")
        for col, (title, res) in zip(st.columns(2), panes):
            with col:
                st.markdown(f"**{title}**" + (" · referral" if res.draft.is_referral else ""))
                render_draft(res)
        st.subheader("4. Sentence check")
        for col, (title, res) in zip(st.columns(2), panes):
            with col:
                st.markdown(f"**{title}**")
                render_checks(res, table=bool(replay))
    else:
        st.subheader("2. Governing regulation")
        render_retrieval(result, gold)
        st.subheader("3. Draft response" if not result.draft.is_referral else "3. Referral")
        render_draft(result)
        st.subheader("4. Sentence check")
        render_checks(result)

    if gold:
        st.caption(f"Gold label: {gold['gold_regulation']} {gold['gold_paragraph'] or gold['gold_section'] or ''}")
    st.caption("Stage timings (ms): " + ", ".join(f"{k} {v:.0f}" for k, v in result.timings_ms.items()))
