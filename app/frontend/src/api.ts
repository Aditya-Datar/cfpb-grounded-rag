// Typed client for the FastAPI backend (app/backend/main.py).

export type Status = "new" | "analyzing" | "in_review" | "scope_review" | "approved" | "referred" | "failed";

export interface Governing { regulation: string; citation: string; heading: string }

export interface CaseSummary {
  id: number; external_id: string | null; company: string | null; product: string | null;
  issue: string | null; state: string | null; status: Status; assigned_to: string | null;
  received_at: string; due_initial: string; due_final: string; days_left: number;
  governing: Governing | null; stage: string | null; scope_out: boolean;
  n_sentences: number | null; n_flagged: number | null; snippet: string;
}

export interface Chunk {
  rank: number; chunk_id: string; score: number; regulation: string; section: string;
  paragraph: string; heading: string; text: string; source_url: string; citation: string;
}

export interface Label { label: string; prob: number; top_k: [string, number][] }

export interface Scope {
  prob_out_of_scope: number; threshold: number; out_of_scope: boolean;
  features: Record<string, number>; model: string;
}

export interface Sentence {
  text: string; cited_chunk_ids: string[]; premise_chunk_ids: string[];
  entail_prob: number | null; contradict_prob: number | null; label: "supported" | "unsupported" | "unchecked";
}

export interface Analysis {
  id: number; origin: string; stage: string; force_draft: boolean; error: string | null;
  classification: { product: Label; issue: Label | null; candidate_regulation: string | null; source: string } | null;
  retrieval: { retriever: string; corpus: string; chunks: Chunk[] } | null;
  scope: Scope | null;
  draft: { model: string; is_referral: boolean } | null;
  generator_model: string | null; verifier: string | null; nli_cutoff: number | null;
  timings_ms: Record<string, number> | null; created_at: string; finished_at: string | null;
}

export interface DraftVersion {
  id: number; version: number; author: string; note: string | null; created_at: string; sentences: Sentence[];
}

export interface CaseEvent { at: string; actor: string; kind: string; detail: string | null }

export interface CaseDetail extends CaseSummary {
  narrative: string; sub_product: string | null; cfpb_date_received: string | null; source: string;
  decision_note: string | null; decided_by: string | null; decided_at: string | null;
  analysis: Analysis | null; drafts: DraftVersion[]; events: CaseEvent[];
  history: { id: number; origin: string; stage: string; created_at: string }[];
}

export interface Health {
  ready: boolean; error: string | null; models: Record<string, string>; database: string;
  nli_cutoff: number; live_drafting: boolean; generator_model: string;
}

export interface Stats {
  total: number; open: number; by_status: Record<string, number>; by_regulation: Record<string, number>;
  overdue: number; due_soon: number; scope_flags: number; drafts: number; sentences: number; flagged_sentences: number;
}

export interface Est { estimate: number; ci95: [number, number] }

export interface About {
  health: Health;
  scope_model: { name: string; threshold: number; source: string;
    report_half: { n: number; n_none: number; auroc: number; true_flags: number; false_flags: number } } | null;
  retrieval: { name: string; n: number; "hit@1": Est; "hit@5": Est; "bm25_hit@5": Est } | null;
  checker: { n: number; labels: string; at_T: Record<string, Est>; at_0_5: Record<string, Est> } | null;
  classifier: { test_n: number; product: { macro_f1: number; accuracy: number };
    issue: { accuracy: number; macro_f1_all_issues: number } } | null;
}

export class ApiError extends Error {}

export function getOfficer(): string {
  try { return localStorage.getItem("officer") || ""; } catch { return ""; }
}
export function setOfficer(name: string) {
  try { localStorage.setItem("officer", name); } catch { /* private mode: name lasts for the session */ }
}

async function call<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const headers: Record<string, string> = { "X-Officer": getOfficer() };
  let body = init?.body;
  if (init?.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(init.json); }
  const res = await fetch(`/api${path}`, { ...init, headers, body });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: { msg: string }) => d.msg).join("; ") : msg;
    } catch { /* not JSON */ }
    throw new ApiError(msg);
  }
  return res.json();
}

export const api = {
  health: () => call<Health>("/health"),
  stats: () => call<Stats>("/stats"),
  about: () => call<About>("/about"),
  cases: () => call<CaseSummary[]>("/cases"),
  case: (id: number) => call<CaseDetail>(`/cases/${id}`),
  create: (body: { narrative: string; company?: string; product?: string; issue?: string; state?: string }) =>
    call<{ id: number }>("/cases", { method: "POST", json: body }),
  analyze: (id: number, force_draft = false) => call<CaseDetail>(`/cases/${id}/analyze`, { method: "POST", json: { force_draft } }),
  saveDraft: (id: number, sentences: { text: string; cited_chunk_ids: string[] }[], note?: string) =>
    call<CaseDetail>(`/cases/${id}/drafts`, { method: "POST", json: { sentences, note } }),
  decide: (id: number, action: "approve" | "refer" | "reopen", note?: string, override_flags = false) =>
    call<CaseDetail>(`/cases/${id}/decision`, { method: "POST", json: { action, note, override_flags } }),
  comment: (id: number, text: string) => call<CaseDetail>(`/cases/${id}/comments`, { method: "POST", json: { text } }),
  assign: (id: number, officer: string | null) => call<CaseDetail>(`/cases/${id}/assign`, { method: "POST", json: { officer } }),
};

// ---- display helpers
export const REG_NAMES: Record<string, string> = {
  E: "Reg E · Electronic fund transfers", Z: "Reg Z · Truth in lending", V: "Reg V · Fair credit reporting",
  F: "Reg F · Debt collection", FCRA: "FCRA · Fair Credit Reporting Act",
};
export const STATUS_LABEL: Record<Status, string> = {
  new: "New", analyzing: "Analyzing", in_review: "Needs review", scope_review: "Scope check",
  approved: "Approved", referred: "Referred", failed: "Failed",
};
export const OPEN_STATUSES: Status[] = ["new", "analyzing", "in_review", "scope_review", "failed"];

export function dueText(daysLeft: number): string {
  if (daysLeft < 0) return `${Math.ceil(-daysLeft)}d overdue`;
  if (daysLeft < 1) return `${Math.max(1, Math.round(daysLeft * 24))}h left`;
  return `${Math.floor(daysLeft)}d left`;
}
export function dueTone(daysLeft: number): "bad" | "warn" | "ok" {
  return daysLeft < 0 ? "bad" : daysLeft <= 3 ? "warn" : "ok";
}
export function fmtDate(iso: string, withTime = false): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}) });
}
