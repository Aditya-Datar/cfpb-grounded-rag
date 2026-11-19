import { Fragment, useEffect, useState } from "react";
import { About, api, REG_NAMES, Stats, STATUS_LABEL, Status } from "../api";
import { Pct } from "../components";

export default function Insights() {
  const [s, setS] = useState<Stats | null>(null);
  const [a, setA] = useState<About | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.stats().then(setS).catch((e) => setErr(e.message));
    api.about().then(setA).catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="notice bad">{err}</div>;
  if (!s || !a) return <div className="empty"><span className="spin" /> Loading…</div>;
  const regMax = Math.max(1, ...Object.values(s.by_regulation));
  const statusMax = Math.max(1, ...Object.values(s.by_status));
  const h = a.health;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Insights &amp; models</h1>
          <p>Workload across all cases, and what the models behind each step are and how well they tested.</p>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head"><h2>Cases by status</h2><span className="faint">{s.total} cases</span></div>
          <div className="card-pad bars">
            {Object.entries(s.by_status).sort((x, y) => y[1] - x[1]).map(([k, v]) => (
              <div className="barrow" key={k}><span>{STATUS_LABEL[k as Status] ?? k}</span>
                <div className="meter"><span style={{ width: `${(v / statusMax) * 100}%` }} /></div><span className="score">{v}</span></div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h2>Governing regulation found</h2><span className="faint">top passage per analysed case</span></div>
          <div className="card-pad bars">
            {Object.entries(s.by_regulation).sort((x, y) => y[1] - x[1]).map(([k, v]) => (
              <div className="barrow" key={k}><span>{REG_NAMES[k]?.split(" · ")[0] ?? k}</span>
                <div className="meter"><span style={{ width: `${(v / regMax) * 100}%`, background: k === "Not analysed" ? "var(--line-strong)" : undefined }} /></div><span className="score">{v}</span></div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card card-pad">
          <h3>Draft quality across cases</h3>
          <div className="row" style={{ gap: 28, marginTop: 10 }}>
            <Big v={s.drafts} k="drafts" /><Big v={s.sentences} k="sentences" />
            <Big v={s.flagged_sentences} k="flagged" tone="bad" />
            <Big v={s.sentences ? `${((s.flagged_sentences / s.sentences) * 100).toFixed(0)}%` : "–"} k="flag rate" />
          </div>
          <p className="faint" style={{ marginBottom: 0 }}>A sentence is flagged when the NLI checker's entailment score against the text it cites is below {h.nli_cutoff.toPrecision(4)}.</p>
        </div>
        <div className="card card-pad">
          <h3>Running on this server</h3>
          <dl className="kv" style={{ marginTop: 10 }}>
            {Object.entries(h.models).filter(([k]) => k !== "state").map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd className="mono">{v}</dd></Fragment>)}
            <dt>database</dt><dd className="mono">{h.database}</dd>
          </dl>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h2>How each step was evaluated</h2><span className="faint">project results files</span></div>
        <div className="card-pad stack">
          <Step n="1" title="Classify (DistilBERT)" body="Fine-tuned on CFPB complaints to predict the product and issue. The product predicts the usual regulation; the app warns when the retrieved passage disagrees." />
          <Step n="2" title="Find the governing section (BM25 over Regs E, F, V, Z and the FCRA)"
            body={a.retrieval_bm25 ? <>On 127 hand-labelled complaints the correct section was the top result for <Pct v={a.retrieval_bm25["hit@1"]} /> and in the top 5 for <Pct v={a.retrieval_bm25["hit@5"]} />. This is the weakest step, which is why the officer sees all five passages.</> : "Results file not found."} />
          <Step n="3" title="Scope check (logistic regression on retrieval confidence)"
            body={a.scope_model ? <>On {a.scope_model.report_half.n} held-out complaints ({a.scope_model.report_half.n_none} outside every covered regulation) it scored AUROC {a.scope_model.report_half.auroc.toFixed(3)}, catching {a.scope_model.report_half.true_flags} of {a.scope_model.report_half.n_none} but also flagging {a.scope_model.report_half.false_flags} covered complaints. So a flag is a prompt for the officer, never an automatic rejection.</> : "Scope model not trained (python -m app.backend.train_scope)."} />
          <Step n="4" title={`Draft (${h.generator_model})`} body="Writes 3 to 6 sentences using only the retrieved passages, tagging each sentence with the passages it relies on. The project's original model was retired by NVIDIA on 2026-10-03." />
          <Step n="5" title="Check every sentence (DeBERTa-v3 NLI, following SummaC)"
            body={a.checker ? <>Validated against {a.checker.n} human-labelled sentence–passage pairs: AUROC {a.checker.auroc.toFixed(3)}. At the 0.5 cutoff it caught {(Number(a.checker.at_0_5.flagged_unsupported_recall) * 100).toFixed(0)}% of unsupported sentences; at the stricter cutoff used here it caught {(Number(a.checker.at_cutoff.flagged_unsupported_recall) * 100).toFixed(0)}% (cutoff tuned on the same pairs; a held-out check is in progress).</> : "Results file not found."} />
          <div className="notice info"><div><b>An assistant, not an adviser.</b> Every draft is reviewed and approved by a compliance officer, who remains responsible for the response. The tool does not give legal advice.</div></div>
        </div>
      </div>
    </div>
  );
}

function Big({ v, k, tone }: { v: number | string; k: string; tone?: "bad" }) {
  return <div><div className="num" style={{ color: tone === "bad" ? "var(--red-dark)" : undefined }}>{v}</div><div className="faint">{k}</div></div>;
}

function Step({ n, title, body }: { n: string; title: string; body: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "28px 1fr", gap: 12 }}>
      <div className="stepnum">{n}</div>
      <div><div style={{ fontWeight: 600 }}>{title}</div><div className="muted">{body}</div></div>
    </div>
  );
}
