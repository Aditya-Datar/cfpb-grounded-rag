import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, CaseDetail, Chunk, DraftVersion, fmtDate, Health, OPEN_STATUSES, REG_NAMES, Sentence } from "../api";
import { Due, Modal, StatusBadge, Toast } from "../components";

const STAGES = [
  { id: "classify", label: "Classify" }, { id: "retrieve", label: "Find regulation" }, { id: "scope", label: "Scope check" },
  { id: "generate", label: "Draft" }, { id: "verify", label: "Check sentences" },
];
// V and the FCRA cover the same ground (credit reporting), so they never count as a mismatch.
const family = (r: string | null | undefined) => (r === "FCRA" ? "V" : r);

export default function CasePage({ health }: { health: Health | null }) {
  const id = Number(useParams().id);
  const [c, setC] = useState<CaseDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sel, setSel] = useState<number | null>(null);
  const [versionIdx, setVersionIdx] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [modal, setModal] = useState<"approve" | "refer" | null>(null);

  const load = useCallback(() => api.case(id).then((d) => { setC(d); setErr(null); }).catch((e) => setErr(e.message)), [id]);
  useEffect(() => { setC(null); setSel(null); setVersionIdx(null); setEditing(false); load(); }, [id, load]);
  useEffect(() => {
    if (c?.status !== "analyzing") return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [c?.status, load]);

  const act = async (fn: () => Promise<CaseDetail>, msg?: string) => {
    setBusy(true);
    try { const d = await fn(); setC(d); if (msg) setToast(msg); return true; }
    catch (e) { setToast((e as Error).message); return false; }
    finally { setBusy(false); }
  };

  if (err) return <div className="notice bad">Could not load case #{id}: {err}</div>;
  if (!c) return <div className="empty"><span className="spin" /> Loading case…</div>;

  const a = c.analysis;
  const chunks = a?.retrieval?.chunks ?? [];
  const drafts = c.drafts;
  const draft: DraftVersion | undefined = drafts[versionIdx ?? drafts.length - 1];
  const isLatest = !draft || draft.id === drafts[drafts.length - 1]?.id;
  const selected = sel != null && draft ? draft.sentences[sel] : null;
  const hitIds = new Set(selected ? (selected.cited_chunk_ids.length ? selected.cited_chunk_ids : selected.premise_chunk_ids) : []);
  const closed = !OPEN_STATUSES.includes(c.status);
  const me = (() => { try { return localStorage.getItem("officer") || ""; } catch { return ""; } })();

  return (
    <div>
      <div className="case-head">
        <div className="crumbs"><Link to="/">Inbox</Link> › Case {c.id}</div>
        <div className="row" style={{ gap: 12 }}>
          <h1>Case {c.id}: {c.company || "Unknown company"}</h1>
          <StatusBadge status={c.status} />
          <Due daysLeft={c.days_left} closed={closed} />
          <div className="spacer" />
          {c.assigned_to !== me && me && !closed && (
            <button className="btn sm" disabled={busy} onClick={() => act(() => api.assign(c.id, me), "Assigned to you")}>Assign to me</button>
          )}
        </div>
        <div className="case-meta">
          <span><em>Issue (as filed)</em>{c.issue || c.product || "Not given"}</span>
          <span><em>CFPB complaint no.</em>{c.external_id ?? "Direct intake"}{c.cfpb_date_received && ` · filed ${c.cfpb_date_received}`}</span>
          <span><em>Received</em>{fmtDate(c.received_at)}</span>
          <span><em>Initial response due</em>{fmtDate(c.due_initial)}</span>
          <span><em>Consumer state</em>{c.state || "–"}</span>
          <span><em>Case owner</em>{c.assigned_to || "Unassigned"}</span>
        </div>
      </div>

      <div className="case-grid">
        <div className="stack">
          {c.status === "new" && (
            <div className="card card-pad stack">
              <h2>Not analysed yet</h2>
              <p className="muted" style={{ margin: 0 }}>
                Run the pipeline to classify the complaint, find the governing regulation section, check scope,
                draft a response that cites it, and check every sentence against the cited text.
              </p>
              {!health?.live_drafting && <div className="notice warn">Live drafting is off on this server (no NVIDIA API key), so analysis will stop before the draft.</div>}
              <div><button className="btn primary" disabled={busy} onClick={() => act(() => api.analyze(c.id), "Analysis started")}>Run analysis</button></div>
            </div>
          )}

          {a && c.status === "analyzing" && <Progress stage={a.stage} />}

          {a?.stage === "failed" && c.status === "failed" && (
            <div className="card card-pad stack">
              <div className="notice bad"><div><b>Analysis failed.</b> {a.error}</div></div>
              <div><button className="btn" disabled={busy} onClick={() => act(() => api.analyze(c.id), "Analysis restarted")}>Retry</button></div>
            </div>
          )}

          {c.status === "scope_review" && a?.scope && (
            <div className="card card-pad stack">
              <div className="notice warn">
                <div>
                  <b>This complaint may fall outside Regulations E, F, V, Z and the FCRA.</b> The scope check scored it{" "}
                  {a.scope.prob_out_of_scope.toFixed(2)} (flag at {a.scope.threshold.toFixed(2)}), so no draft was written.
                  The check catches most out-of-scope complaints but also flags many covered ones, so it is your call.
                </div>
              </div>
              <div className="row">
                <button className="btn" disabled={busy} onClick={() => setModal("refer")}>Refer to specialist</button>
                <button className="btn primary" disabled={busy || !health?.live_drafting} onClick={() => act(() => api.analyze(c.id, true), "Drafting despite the scope flag")}>
                  Draft anyway
                </button>
              </div>
            </div>
          )}

          {draft && (
            <DraftCard
              c={c} draft={draft} drafts={drafts} chunks={chunks} isLatest={isLatest} sel={sel} setSel={setSel}
              editing={editing} setEditing={setEditing} busy={busy} closed={closed}
              setVersion={(i) => { setVersionIdx(i); setSel(null); setEditing(false); }}
              onSave={async (sents, note) => {
                const ok = await act(() => api.saveDraft(c.id, sents, note), "New version saved and re-checked");
                if (ok) { setEditing(false); setVersionIdx(null); setSel(null); }
              }}
              onApprove={() => setModal("approve")} onRefer={() => setModal("refer")}
              onReopen={() => act(() => api.decide(c.id, "reopen"), "Case reopened")}
              onCopy={() => { navigator.clipboard?.writeText(draft.sentences.map((s) => s.text).join(" ")); setToast("Draft copied"); }}
            />
          )}

          {closed && c.decision_note && (
            <div className="card card-pad">
              <h3>Decision</h3>
              <p style={{ margin: "8px 0 0" }}>{c.status === "approved" ? "Approved" : "Referred"} by <b>{c.decided_by}</b>{c.decided_at && ` on ${fmtDate(c.decided_at, true)}`}: {c.decision_note}</p>
            </div>
          )}
          {closed && !draft && (
            <div className="card card-pad row"><span className="muted">This case is {c.status}.</span><div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => act(() => api.decide(c.id, "reopen"), "Case reopened")}>Reopen</button></div>
          )}

          <Activity c={c} busy={busy} onComment={(t) => act(() => api.comment(c.id, t), "Comment added")} />
        </div>

        <div className="stack">
          <ComplaintCard c={c} />
          {a?.classification && <TriageCard a={a} />}
          {a?.scope && c.status !== "scope_review" && <ScopeCard scope={a.scope} />}
          {chunks.length > 0 && <Passages chunks={chunks} hit={hitIds} candidate={a?.classification?.candidate_regulation ?? null} />}
        </div>
      </div>

      {modal && (
        <DecisionModal
          kind={modal} flagged={draft?.sentences.filter((s) => s.label === "unsupported").length ?? 0}
          onClose={() => setModal(null)}
          onSubmit={async (note, override) => {
            const ok = await act(() => api.decide(c.id, modal, note, override), modal === "approve" ? "Response approved" : "Case referred");
            if (ok) setModal(null);
          }}
        />
      )}
      {toast && <Toast text={toast} onDone={() => setToast(null)} />}
    </div>
  );
}

function Progress({ stage }: { stage: string }) {
  const i = STAGES.findIndex((s) => s.id === stage);
  return (
    <div className="card card-pad stack">
      <div className="row"><span className="spin" style={{ color: "var(--blue)" }} /><h2>Analyzing</h2>
        <span className="faint">{stage === "queued" ? "Waiting for the worker…" : stage === "generate" ? "Drafting on the NVIDIA API can take several minutes." : ""}</span></div>
      <div className="steps">
        {STAGES.map((s, j) => (
          <div key={s.id} className={`step ${j < i ? "done" : j === i ? "now" : ""}`}><div className="bar" />{s.label}</div>
        ))}
      </div>
      <p className="faint" style={{ margin: 0 }}>You can leave this page; the case moves to “Needs review” when the draft is ready.</p>
    </div>
  );
}

interface DraftCardProps {
  c: CaseDetail; draft: DraftVersion; drafts: DraftVersion[]; chunks: Chunk[]; isLatest: boolean;
  sel: number | null; setSel: (i: number | null) => void; editing: boolean; setEditing: (b: boolean) => void;
  busy: boolean; closed: boolean; setVersion: (i: number) => void;
  onSave: (s: { text: string; cited_chunk_ids: string[] }[], note?: string) => void;
  onApprove: () => void; onRefer: () => void; onReopen: () => void; onCopy: () => void;
}

function DraftCard(p: DraftCardProps) {
  const { c, draft, chunks } = p;
  const flagged = draft.sentences.filter((s) => s.label === "unsupported").length;
  const unchecked = draft.sentences.filter((s) => s.label === "unchecked").length;
  const pIndex = useMemo(() => Object.fromEntries(chunks.map((ch, i) => [ch.chunk_id, i + 1])), [chunks]);
  const a = c.analysis;
  const replay = a?.origin.startsWith("replay:");

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>Draft response</h2>
          <div className="faint">
            v{draft.version} by {draft.author} · {fmtDate(draft.created_at, true)}
            {draft.author === "AI draft" && a?.generator_model && ` · ${a.generator_model}${replay ? " (saved run)" : ""}`}
          </div>
        </div>
        <div className="row">
          {p.drafts.length > 1 && (
            <select className="select" style={{ width: 150 }} value={p.drafts.findIndex((d) => d.id === draft.id)} onChange={(e) => p.setVersion(Number(e.target.value))} aria-label="Version">
              {p.drafts.map((d, i) => <option key={d.id} value={i}>v{d.version} · {d.author}</option>)}
            </select>
          )}
          <button className="btn sm" onClick={p.onCopy}>Copy</button>
          {!p.closed && p.isLatest && !p.editing && <button className="btn sm" onClick={() => p.setEditing(true)}>Edit</button>}
        </div>
      </div>

      {!p.editing && (
        <div style={{ padding: "12px 18px 0" }}>
          {flagged > 0 ? (
            <div className="notice bad"><div><b>{flagged} of {draft.sentences.length} sentences are not supported</b> by the passage they cite (entailment below {a?.nli_cutoff?.toPrecision(4) ?? "the cutoff"}). Fix or remove them, or approve with a written justification.</div></div>
          ) : unchecked === draft.sentences.length ? (
            <div className="notice warn">These sentences were not checked (the NLI model is not loaded).</div>
          ) : (
            <div className="notice ok"><div><b>Every sentence is supported</b> by the passage it cites. That does not mean the passage is the right one; confirm the governing section on the right.</div></div>
          )}
        </div>
      )}

      {p.editing ? (
        <Editor draft={draft} chunks={chunks} pIndex={pIndex} busy={p.busy} onCancel={() => p.setEditing(false)} onSave={p.onSave} />
      ) : (
        <div className="sentences" style={{ marginTop: 10 }}>
          {draft.sentences.map((s, i) => (
            <SentenceRow key={i} s={s} i={i} sel={p.sel === i} pIndex={pIndex} chunks={chunks} onClick={() => p.setSel(p.sel === i ? null : i)} />
          ))}
        </div>
      )}

      {!p.editing && (
        <div className="decision">
          {!p.closed ? (
            <>
              <span className="faint">{p.isLatest ? "Click a sentence to see the passage it relies on." : "Viewing an older version."}</span>
              <div className="spacer" />
              <button className="btn danger" disabled={p.busy} onClick={p.onRefer}>Refer</button>
              <button className="btn good" disabled={p.busy || !p.isLatest || c.status !== "in_review"} onClick={p.onApprove}>Approve response</button>
            </>
          ) : (
            <>
              <span className="muted">{c.status === "approved" ? "Approved" : "Referred"}{c.decided_by && ` by ${c.decided_by}`}.</span>
              <div className="spacer" />
              <button className="btn" disabled={p.busy} onClick={p.onReopen}>Reopen</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function SentenceRow({ s, i, sel, pIndex, chunks, onClick }: { s: Sentence; i: number; sel: boolean; pIndex: Record<string, number>; chunks: Chunk[]; onClick: () => void }) {
  const cites = s.cited_chunk_ids.length ? s.cited_chunk_ids : [];
  return (
    <div className={`sent ${s.label} ${sel ? "sel" : ""}`} onClick={onClick} role="button" tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClick()}>
      <div className="idx">{i + 1}</div>
      <div>
        <div className="txt">{s.text}</div>
        <div className="cites">
          {cites.length ? cites.map((cid) => {
            const ch = chunks.find((x) => x.chunk_id === cid);
            return <span key={cid} className={`chip ${sel ? "on" : ""}`}>P{pIndex[cid]} · {ch?.citation ?? cid}</span>;
          }) : <span className="chip">No citation · checked against all passages</span>}
        </div>
      </div>
      <div className="verdict">
        {s.label === "supported" && <span className="badge tone-ok">Supported</span>}
        {s.label === "unsupported" && <span className="badge tone-bad">Flagged</span>}
        {s.label === "unchecked" && <span className="badge">Not checked</span>}
        {s.entail_prob != null && <span className="score" title="Probability the cited text entails this sentence (DeBERTa NLI)">entail {s.entail_prob.toFixed(3)}</span>}
      </div>
    </div>
  );
}

function Editor({ draft, chunks, pIndex, busy, onCancel, onSave }: {
  draft: DraftVersion; chunks: Chunk[]; pIndex: Record<string, number>; busy: boolean;
  onCancel: () => void; onSave: (s: { text: string; cited_chunk_ids: string[] }[], note?: string) => void;
}) {
  const [rows, setRows] = useState(draft.sentences.map((s) => ({ text: s.text, cited_chunk_ids: [...s.cited_chunk_ids], label: s.label })));
  const [note, setNote] = useState("");
  const update = (i: number, patch: Partial<(typeof rows)[number]>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const valid = rows.length > 0 && rows.every((r) => r.text.trim());
  return (
    <div>
      <div className="notice info" style={{ margin: "12px 18px" }}>
        Edit, add or remove sentences and choose which passages each one relies on. Saving creates a new version and re-checks every sentence.
      </div>
      {rows.map((r, i) => (
        <div className="edit-row" key={i}>
          <div className="idx faint" style={{ paddingTop: 8 }}>{i + 1}</div>
          <div>
            <textarea className="textarea" rows={2} value={r.text} onChange={(e) => update(i, { text: e.target.value })}
              style={{ borderColor: r.label === "unsupported" ? "var(--red-dark)" : undefined }} />
            <div className="cite-pick">
              <span className="faint" style={{ marginRight: 4 }}>Relies on:</span>
              {chunks.map((ch) => {
                const on = r.cited_chunk_ids.includes(ch.chunk_id);
                return (
                  <button key={ch.chunk_id} type="button" className={`chip ${on ? "on" : ""}`} title={ch.citation}
                    onClick={() => update(i, { cited_chunk_ids: on ? r.cited_chunk_ids.filter((x) => x !== ch.chunk_id) : [...r.cited_chunk_ids, ch.chunk_id] })}>
                    P{pIndex[ch.chunk_id]}
                  </button>
                );
              })}
            </div>
          </div>
          <button className="btn ghost sm" title="Remove sentence" onClick={() => setRows(rows.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <div style={{ padding: "12px 18px", display: "grid", gap: 10 }}>
        <div><button className="btn sm" onClick={() => setRows([...rows, { text: "", cited_chunk_ids: [], label: "unchecked" }])}>+ Add sentence</button></div>
        <input className="input" placeholder="What changed and why (optional, goes in the case history)" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="decision">
        <span className="faint">{busy ? "Re-checking sentences against the regulation text…" : `${rows.length} sentences`}</span>
        <div className="spacer" />
        <button className="btn" disabled={busy} onClick={onCancel}>Cancel</button>
        <button className="btn primary" disabled={busy || !valid}
          onClick={() => onSave(rows.map((r) => ({ text: r.text.trim(), cited_chunk_ids: r.cited_chunk_ids })), note.trim() || undefined)}>
          {busy && <span className="spin" />} Save &amp; re-check
        </button>
      </div>
    </div>
  );
}

function ComplaintCard({ c }: { c: CaseDetail }) {
  const [full, setFull] = useState(false);
  const long = c.narrative.length > 700;
  return (
    <div className="card">
      <div className="card-head"><h2>Consumer complaint</h2><span className="faint">{c.product}</span></div>
      <div className="card-pad">
        <div className={`narrative ${long && !full ? "clamp" : ""}`}>{c.narrative}</div>
        {long && <button className="btn ghost sm" style={{ marginTop: 6, paddingLeft: 0 }} onClick={() => setFull(!full)}>{full ? "Show less" : "Show full complaint"}</button>}
        <p className="faint" style={{ marginBottom: 0 }}>Personal details are redacted by the CFPB (XXXX).</p>
      </div>
    </div>
  );
}

function TriageCard({ a }: { a: NonNullable<CaseDetail["analysis"]> }) {
  const cl = a.classification!;
  const stub = cl.source === "stub";
  return (
    <div className="card">
      <div className="card-head"><h2>Triage</h2><span className="faint">{stub ? "placeholder classifier" : "DistilBERT"}</span></div>
      <div className="card-pad stack" style={{ gap: 12 }}>
        <Pred title="Product" p={cl.product} />
        {cl.issue && <Pred title="Issue" p={cl.issue} />}
        <div className="faint">Usual regulation for this product: <b style={{ color: "var(--ink)" }}>{cl.candidate_regulation ? REG_NAMES[cl.candidate_regulation] ?? cl.candidate_regulation : "none"}</b></div>
      </div>
    </div>
  );
}

function Pred({ title, p }: { title: string; p: { label: string; prob: number; top_k: [string, number][] } }) {
  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}><span className="faint">{title}</span><span className="score">{(p.prob * 100).toFixed(0)}%</span></div>
      <div style={{ fontWeight: 600, margin: "2px 0 5px" }}>{p.label}</div>
      <div className="meter"><span style={{ width: `${p.prob * 100}%` }} /></div>
      {p.top_k.length > 1 && <div className="faint" style={{ marginTop: 5 }}>Next: {p.top_k.slice(1).map(([l, v]) => `${l} (${(v * 100).toFixed(0)}%)`).join(" · ")}</div>}
    </div>
  );
}

function ScopeCard({ scope }: { scope: NonNullable<NonNullable<CaseDetail["analysis"]>["scope"]> }) {
  return (
    <div className="card">
      <div className="card-head"><h2>Scope check</h2>
        {scope.out_of_scope ? <span className="badge tone-warn">May be out of scope</span> : <span className="badge tone-ok">In scope</span>}
      </div>
      <div className="card-pad gauge">
        <div className="track" style={{ ["--thr" as string]: `${scope.threshold * 100}%` }}>
          <div className="thr" style={{ left: `${scope.threshold * 100}%` }} title={`flag at ${scope.threshold.toFixed(2)}`} />
          <div className="mark" style={{ left: `${scope.prob_out_of_scope * 100}%` }} />
        </div>
        <div className="row faint" style={{ justifyContent: "space-between" }}><span>covered</span><span>score {scope.prob_out_of_scope.toFixed(2)} · flag at {scope.threshold.toFixed(2)}</span><span>outside</span></div>
        {scope.out_of_scope && <div className="faint">A draft exists anyway. Check that the cited regulation really governs this complaint before approving.</div>}
      </div>
    </div>
  );
}

function Passages({ chunks, hit, candidate }: { chunks: Chunk[]; hit: Set<string>; candidate: string | null }) {
  const top = chunks[0];
  const mismatch = candidate && top && family(top.regulation) !== family(candidate);
  return (
    <div className="card">
      <div className="card-head"><h2>Regulation passages</h2><span className="faint">top {chunks.length} retrieved</span></div>
      {mismatch && (
        <div className="notice warn" style={{ margin: "12px 16px 0" }}>
          The top passage is from {REG_NAMES[top.regulation] ?? top.regulation}, but this product is usually governed by {REG_NAMES[candidate!] ?? candidate}. Check that the right regulation was found.
        </div>
      )}
      <div style={{ marginTop: mismatch ? 8 : 0 }}>
        {chunks.map((ch, i) => (
          <details key={ch.chunk_id} className={`passage ${hit.has(ch.chunk_id) ? "hit" : ""}`} open={hit.has(ch.chunk_id) || (hit.size === 0 && i === 0)}>
            <summary>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span><b>P{i + 1}</b> <span className="mono">{ch.citation}</span></span>
                <span className="chip">{ch.regulation === "FCRA" ? "FCRA" : `Reg ${ch.regulation}`}</span>
              </div>
              <div className="faint">{ch.heading}</div>
            </summary>
            <div className="ptext">{ch.text}</div>
            <div style={{ padding: "0 16px 12px" }}><a href={ch.source_url} target="_blank" rel="noreferrer">Open official text ↗</a></div>
          </details>
        ))}
      </div>
    </div>
  );
}

const EVENT_LABEL: Record<string, string> = {
  imported: "Imported", created: "Created", analysis_started: "Analysis started", analysis_done: "Analysis complete",
  analysis_failed: "Analysis failed", scope_flag: "Scope flag", edited: "Draft edited", approve: "Approved",
  refer: "Referred", reopen: "Reopened", comment: "Note", assigned: "Assignment",
};

function Activity({ c, busy, onComment }: { c: CaseDetail; busy: boolean; onComment: (t: string) => Promise<boolean> }) {
  const [text, setText] = useState("");
  return (
    <div className="card">
      <div className="card-head"><h2>Case history and notes</h2><span className="faint">{c.events.length} entries</span></div>
      <div className="card-pad">
        <form className="row" style={{ marginBottom: 10, flexWrap: "nowrap" }} onSubmit={async (e) => { e.preventDefault(); if (text.trim() && (await onComment(text.trim()))) setText(""); }}>
          <input className="input" placeholder="Add a note for the team…" value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} />
          <button className="btn" disabled={busy || !text.trim()}>Add</button>
        </form>
        <div className="timeline">
          {c.events.map((e, i) => (
            <div className={`tl k-${e.kind}`} key={i}>
              <div className="what"><b>{EVENT_LABEL[e.kind] ?? e.kind}</b> · {e.actor}</div>
              {e.detail && <div className="muted" style={{ fontSize: 14 }}>{e.detail}</div>}
              <div className="when">{fmtDate(e.at, true)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DecisionModal({ kind, flagged, onClose, onSubmit }: { kind: "approve" | "refer"; flagged: number; onClose: () => void; onSubmit: (note: string, override: boolean) => void }) {
  const [note, setNote] = useState("");
  const [override, setOverride] = useState(false);
  const needNote = kind === "refer" || flagged > 0;
  const ok = (!needNote || note.trim()) && (kind === "refer" || flagged === 0 || override);
  return (
    <Modal onClose={onClose}>
      <h2>{kind === "approve" ? "Approve this response" : "Refer this case"}</h2>
      {kind === "approve" ? (
        flagged > 0 ? (
          <>
            <div className="notice bad"><div><b>{flagged} sentence{flagged > 1 ? "s are" : " is"} flagged</b> as not supported by the cited regulation text.</div></div>
            <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} /> I checked the flagged sentences and they are correct.</label>
          </>
        ) : <p className="muted" style={{ margin: 0 }}>The approved draft and your name are recorded in the case history. You remain responsible for what is sent.</p>
      ) : <p className="muted" style={{ margin: 0 }}>Send the case to a specialist (legal or compliance) instead of answering from this draft.</p>}
      <label className="field">
        {kind === "refer" ? "Reason for referral" : flagged > 0 ? "Justification" : "Note (optional)"}
        <textarea className="textarea" rows={3} value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
      </label>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className={`btn ${kind === "approve" ? "good" : "primary"}`} disabled={!ok} onClick={() => onSubmit(note.trim(), override)}>
          {kind === "approve" ? "Approve" : "Refer"}
        </button>
      </div>
    </Modal>
  );
}
