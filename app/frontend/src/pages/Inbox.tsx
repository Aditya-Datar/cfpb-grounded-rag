import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, CaseSummary, OPEN_STATUSES, Status } from "../api";
import { Due, StatusBadge } from "../components";

type Tab = "open" | Status | "all";
const TABS: { id: Tab; label: string }[] = [
  { id: "open", label: "All open" }, { id: "in_review", label: "Needs review" }, { id: "scope_review", label: "Scope check" },
  { id: "new", label: "New" }, { id: "analyzing", label: "Analyzing" }, { id: "approved", label: "Approved" },
  { id: "referred", label: "Referred" }, { id: "failed", label: "Failed" },
];

export default function Inbox({ reviewOnly = false }: { reviewOnly?: boolean }) {
  const [rows, setRows] = useState<CaseSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(reviewOnly ? "in_review" : "open");
  const [q, setQ] = useState("");
  const [reg, setReg] = useState("");
  const [mine, setMine] = useState(false);
  const nav = useNavigate();

  useEffect(() => { setTab(reviewOnly ? "in_review" : "open"); }, [reviewOnly]);
  useEffect(() => {
    let alive = true;
    const load = () => api.cases().then((r) => { if (alive) { setRows(r); setErr(null); } })
      .catch((e) => alive && setErr(String(e.message || e)));
    load();
    const t = setInterval(load, 10000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const officer = (() => { try { return localStorage.getItem("officer") || ""; } catch { return ""; } })();
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: rows?.length ?? 0, open: 0 };
    rows?.forEach((r) => { c[r.status] = (c[r.status] ?? 0) + 1; if (OPEN_STATUSES.includes(r.status)) c.open++; });
    return c;
  }, [rows]);

  const shown = useMemo(() => {
    if (!rows) return [];
    const needle = q.trim().toLowerCase();
    return rows
      .filter((r) => tab === "all" || (tab === "open" ? OPEN_STATUSES.includes(r.status) : r.status === tab))
      .filter((r) => !reg || (reg === "none" ? !r.governing : r.governing?.regulation === reg))
      .filter((r) => !mine || r.assigned_to === officer)
      .filter((r) => !needle || [r.company, r.product, r.issue, r.external_id, String(r.id), r.snippet, r.governing?.citation]
        .some((f) => f?.toLowerCase().includes(needle)))
      .sort((a, b) => a.days_left - b.days_left);
  }, [rows, tab, q, reg, mine, officer]);

  const open = rows?.filter((r) => OPEN_STATUSES.includes(r.status)) ?? [];
  const reviewTab = tab === "in_review" || tab === "scope_review";

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>{reviewOnly ? "Needs review" : "Complaint inbox"}</h1>
          <p>Sorted by response deadline. Companies owe the CFPB an initial response within 15 days.</p>
        </div>
        <Link className="btn primary" to="/new">Enter new complaint</Link>
      </div>

      {!reviewOnly && (
        <div className="stats">
          <Stat k="Open cases" v={open.length} s={`${rows?.length ?? 0} total`} />
          <Stat k="Drafts to review" v={counts.in_review ?? 0} s="AI draft ready" />
          <Stat k="Scope checks" v={counts.scope_review ?? 0} s="may be outside our regulations" tone="warn" />
          <Stat k="Due in 3 days" v={open.filter((r) => r.days_left >= 0 && r.days_left <= 3).length} s="initial response" tone="warn" />
          <Stat k="Overdue" v={open.filter((r) => r.days_left < 0).length} s="past 15 days" tone="bad" />
        </div>
      )}

      <div className="card">
        <div className="toolbar">
          <div className="tabs">
            {TABS.filter((t) => !reviewOnly || t.id === "in_review" || t.id === "scope_review").map((t) => (
              <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
                {t.label}<span className="n">{counts[t.id] ?? 0}</span>
              </button>
            ))}
          </div>
          <div className="spacer" />
          <select className="select" style={{ width: 190 }} value={reg} onChange={(e) => setReg(e.target.value)} aria-label="Regulation">
            <option value="">All regulations</option>
            <option value="E">Reg E</option><option value="F">Reg F</option><option value="V">Reg V</option>
            <option value="Z">Reg Z</option><option value="FCRA">FCRA</option><option value="none">Not analysed yet</option>
          </select>
          <label className="row" style={{ gap: 6, cursor: "pointer", fontSize: 14 }}>
            <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Assigned to me
          </label>
          <input className="input" style={{ width: 240 }} placeholder="Search company, issue, citation…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {err && <div className="notice bad" style={{ margin: 14 }}>Could not load cases: {err}</div>}
        {!rows && !err && <div className="empty"><span className="spin" /> Loading cases…</div>}
        {rows && shown.length === 0 && <div className="empty">{reviewTab ? "Nothing waiting for review." : "No cases match."}</div>}
        {shown.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Case</th><th>Complaint</th><th className="hide-sm">Governing section</th>
                  <th className="hide-sm">Draft check</th><th>Status</th><th>Due</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.id} onClick={() => nav(`/cases/${r.id}`)}>
                    <td>
                      <div className="cell-title"><Link to={`/cases/${r.id}`} onClick={(e) => e.stopPropagation()}>#{r.id}</Link></div>
                      <div className="faint">{r.external_id ? `CFPB ${r.external_id}` : "Intake"}</div>
                    </td>
                    <td>
                      <div className="cell-title">{r.company || "Unknown company"}</div>
                      <div className="cell-sub">{r.issue || r.product || r.snippet}</div>
                    </td>
                    <td className="hide-sm">
                      {r.governing ? (
                        <><div className="mono">{r.governing.citation}</div><div className="faint">{r.governing.regulation === "FCRA" ? "FCRA" : `Reg ${r.governing.regulation}`}{r.scope_out ? " · scope flag" : ""}</div></>
                      ) : <span className="faint">–</span>}
                    </td>
                    <td className="hide-sm">
                      {r.n_sentences ? (
                        r.n_flagged ? <span className="badge plain tone-bad">{r.n_flagged} of {r.n_sentences} flagged</span>
                          : <span className="badge plain tone-ok">{r.n_sentences} of {r.n_sentences} supported</span>
                      ) : <span className="faint">–</span>}
                    </td>
                    <td><StatusBadge status={r.status} />{r.assigned_to && <div className="faint" style={{ marginTop: 4 }}>{r.assigned_to}</div>}</td>
                    <td><Due daysLeft={r.days_left} closed={!OPEN_STATUSES.includes(r.status)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ k, v, s, tone }: { k: string; v: number; s: string; tone?: "warn" | "bad" }) {
  return (
    <div className={`stat ${tone && v > 0 ? tone : ""}`}>
      <div className="k">{k}</div>
      <div className="v" style={{ color: tone === "bad" && v > 0 ? "var(--red-dark)" : undefined }}>{v}</div>
      <div className="s">{s}</div>
    </div>
  );
}
