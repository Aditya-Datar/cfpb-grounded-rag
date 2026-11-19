import { ReactNode, useEffect, useRef } from "react";
import { dueText, dueTone, Status, STATUS_LABEL } from "./api";

const STATUS_TONE: Record<Status, string> = {
  new: "tone-outline", analyzing: "tone-accent", in_review: "tone-violet", scope_review: "tone-warn",
  approved: "tone-ok", referred: "", failed: "tone-bad",
};

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge ${STATUS_TONE[status]}`}>{STATUS_LABEL[status]}</span>;
}

const DUE_TONE = { ok: "tone-outline", warn: "tone-warn", bad: "tone-bad" } as const;

export function Due({ daysLeft, closed }: { daysLeft: number; closed?: boolean }) {
  if (closed) return <span className="faint">Closed</span>;
  return <span className={`badge plain ${DUE_TONE[dueTone(daysLeft)]}`}>{dueText(daysLeft)}</span>;
}

export function Modal({ children, onClose }: { children: ReactNode; onClose?: () => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className="modal" role="dialog" aria-modal="true">{children}</div>
    </div>
  );
}

export function Toast({ text, onDone }: { text: string; onDone: () => void }) {
  // The parent re-renders while it polls; keep the timer tied to the text, not to onDone's identity.
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => { const t = setTimeout(() => done.current(), 3200); return () => clearTimeout(t); }, [text]);
  return <div className="toast" role="status">{text}</div>;
}

export function Pct({ v }: { v: number | null | undefined }) {
  return <>{v == null ? "–" : `${(v * 100).toFixed(1)}%`}</>;
}
