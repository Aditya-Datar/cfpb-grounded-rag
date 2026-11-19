import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Health } from "../api";

// CFPB product categories the classifier was trained on (src/cfpb/config.py PRODUCT_TO_REGULATION).
const PRODUCTS = [
  "Credit reporting or other personal consumer reports", "Debt collection", "Credit card", "Mortgage",
  "Checking or savings account", "Money transfer, virtual currency, or money service", "Vehicle loan or lease",
  "Student loan", "Payday loan, title loan, personal loan, or advance loan", "Prepaid card", "Debt or credit management",
];

export default function NewCase({ health }: { health: Health | null }) {
  const nav = useNavigate();
  const [f, setF] = useState({ narrative: "", company: "", product: "", issue: "", state: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const words = f.narrative.trim() ? f.narrative.trim().split(/\s+/).length : 0;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const { id } = await api.create({
        narrative: f.narrative, company: f.company || undefined, product: f.product || undefined,
        issue: f.issue || undefined, state: f.state || undefined,
      });
      nav(`/cases/${id}`);
    } catch (e2) { setErr((e2 as Error).message); setBusy(false); }
  };

  return (
    <div style={{ maxWidth: 860 }}>
      <div className="page-head">
        <div>
          <h1>New complaint</h1>
          <p>Paste a complaint received from the CFPB portal. Analysis starts as soon as you submit.</p>
        </div>
      </div>
      {health && !health.live_drafting && (
        <div className="notice warn" style={{ marginBottom: 14 }}>
          Live drafting is off on this server (no NVIDIA API key). Classification, regulation lookup and the scope check still run.
        </div>
      )}
      <form className="card card-pad stack" onSubmit={submit}>
        <label className="field">
          Complaint narrative
          <span className="hint">The consumer's own words. At least 20 characters.</span>
          <textarea className="textarea" rows={10} value={f.narrative} onChange={set("narrative")} required minLength={20}
            placeholder="e.g. On March 3 someone withdrew $640 from my checking account at an ATM I have never used. I reported it to the bank the next day and they told me…" />
          <span className="hint">{words} words{words > 1200 ? " · only the first 1,200 words are used for drafting" : ""}</span>
        </label>
        <div className="grid-2">
          <label className="field">Company<input className="input" value={f.company} onChange={set("company")} maxLength={200} placeholder="e.g. Example Bank, N.A." /></label>
          <label className="field">Product (as filed)
            <select className="select" value={f.product} onChange={set("product")}>
              <option value="">Not given — let the classifier decide</option>
              {PRODUCTS.map((p) => <option key={p}>{p}</option>)}
            </select>
          </label>
          <label className="field">Issue (as filed)<input className="input" value={f.issue} onChange={set("issue")} maxLength={300} placeholder="optional" /></label>
          <label className="field">Consumer state<input className="input" value={f.state} onChange={set("state")} maxLength={8} placeholder="e.g. CA" /></label>
        </div>
        {err && <div className="notice bad">{err}</div>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="btn" type="button" onClick={() => nav(-1)}>Cancel</button>
          <button className="btn primary" disabled={busy || f.narrative.trim().length < 20}>{busy && <span className="spin" />} Create case &amp; analyze</button>
        </div>
      </form>
    </div>
  );
}
