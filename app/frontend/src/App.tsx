import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import { api, getOfficer, Health, setOfficer, Stats } from "./api";
import Inbox from "./pages/Inbox";
import CasePage from "./pages/CasePage";
import NewCase from "./pages/NewCase";
import Insights from "./pages/Insights";
import { Modal } from "./components";

export default function App() {
  const [officer, setName] = useState(getOfficer());
  const [askName, setAskName] = useState(!getOfficer());
  const [health, setHealth] = useState<Health | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () => {
      api.health().then((h) => alive && setHealth(h)).catch(() => alive && setHealth(null));
      api.stats().then((s) => alive && setStats(s)).catch(() => {});
    };
    tick();
    const t = setInterval(tick, 8000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const review = (stats?.by_status.in_review ?? 0) + (stats?.by_status.scope_review ?? 0);

  return (
    <div className="shell">
      <div className="strip">
        <div className="wrap">
          <span>Internal tool for compliance staff. Drafts are prepared for officer review and are not legal advice.</span>
          <span>Response deadlines follow CFPB timelines: initial response within 15 days, final within 60.</span>
        </div>
      </div>
      <header className="header">
        <div className="wrap">
          <Link to="/" className="brand">
            <div className="brand-mark">§</div>
            <div>
              <div className="brand-name">Complaint Review</div>
              <div className="brand-sub">Consumer complaint response desk</div>
            </div>
          </Link>
          <nav className="nav">
            <NavLink to="/" end>Inbox {stats && <span className="count">{stats.open}</span>}</NavLink>
            <NavLink to="/review">Needs review {stats && <span className="count">{review}</span>}</NavLink>
            <NavLink to="/new">New complaint</NavLink>
            <NavLink to="/insights">Reports &amp; models</NavLink>
          </nav>
          <div className="who">
            <SystemState health={health} />
            <span>Signed in as <b>{officer || "—"}</b></span>
            <button onClick={() => setAskName(true)}>Change</button>
          </div>
        </div>
      </header>
      <main className="main">
        <div className="wrap">
          <Routes>
            <Route path="/" element={<Inbox />} />
            <Route path="/review" element={<Inbox reviewOnly />} />
            <Route path="/cases/:id" element={<CasePage health={health} />} />
            <Route path="/new" element={<NewCase health={health} />} />
            <Route path="/insights" element={<Insights />} />
          </Routes>
        </div>
      </main>
      <footer className="footer">
        <div className="wrap">
          CSCI 544 Group 36 · Regulation-grounded triage and response drafting · Regulations E, F, V, Z and the FCRA from the eCFR and U.S. Code
        </div>
      </footer>
      {askName && (
        <OfficerModal initial={officer} onDone={(n) => { setOfficer(n); setName(n); setAskName(false); }}
          onCancel={officer ? () => setAskName(false) : undefined} />
      )}
    </div>
  );
}

function SystemState({ health }: { health: Health | null }) {
  if (!health) return <span className="sysstate bad"><i />Server offline</span>;
  if (health.error) return <span className="sysstate bad" title={health.error}><i />Models failed to load</span>;
  if (!health.ready) return <span className="sysstate warn"><i />Loading models</span>;
  if (!health.live_drafting) return <span className="sysstate warn" title="Set NVIDIA_API_KEY in .env"><i />Ready · drafting off</span>;
  return <span className="sysstate"><i />System ready</span>;
}

function OfficerModal({ initial, onDone, onCancel }: { initial: string; onDone: (n: string) => void; onCancel?: () => void }) {
  const [name, setName] = useState(initial);
  return (
    <Modal onClose={onCancel}>
      <h2>Sign in</h2>
      <p className="muted" style={{ margin: 0 }}>
        Enter your name. It is recorded on every edit and decision in the case history. (Demo: no password.)
      </p>
      <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) onDone(name.trim()); }} className="stack">
        <label className="field">Full name
          <input className="input" autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        </label>
        <div className="row">
          <button className="btn primary" disabled={!name.trim()}>Continue</button>
          {onCancel && <button type="button" className="btn" onClick={onCancel}>Cancel</button>}
        </div>
      </form>
    </Modal>
  );
}
