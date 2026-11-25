"""FastAPI backend for the compliance officer app.

    uvicorn app.backend.main:app --port 8000        # from the repo root

Serves the JSON API under /api and, once built (npm run build in app/frontend),
the React app itself. The officer's name comes from the X-Officer header (the
frontend asks for it once); there is no real authentication, as this is a demo.
"""
import json
import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import selectinload

from app.backend import config, engine as eng
from app.backend.db import Analysis, Case, DraftVersion, Session, init_db, log_event, now

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
OPEN = ("new", "analyzing", "in_review", "scope_review", "failed")


@asynccontextmanager
async def lifespan(_):
    init_db()
    eng.start()
    yield


app = FastAPI(title="CFPB complaint review", lifespan=lifespan)


# ------------------------------------------------------------------ helpers
def officer(x_officer: str | None) -> str:
    name = (x_officer or "").strip()
    return name[:80] if name else "Officer"


def deadlines(c: Case) -> dict:
    initial = c.received_at + timedelta(days=config.INITIAL_RESPONSE_DAYS)
    final = c.received_at + timedelta(days=config.FINAL_RESPONSE_DAYS)
    return {"due_initial": initial.isoformat(), "due_final": final.isoformat(),
            "days_left": (initial - now()).total_seconds() / 86400}


def latest(c: Case) -> tuple[Analysis | None, DraftVersion | None]:
    return (c.analyses[-1] if c.analyses else None), (c.drafts[-1] if c.drafts else None)


def governing(a: Analysis | None) -> dict | None:
    if not a or not a.retrieval or not a.retrieval.get("chunks"):
        return None
    top = a.retrieval["chunks"][0]
    return {"regulation": top["regulation"], "citation": top["citation"], "heading": top["heading"]}


def summary(c: Case) -> dict:
    a, d = latest(c)
    flagged = sum(s["label"] == "unsupported" for s in d.sentences) if d else None
    return {"id": c.id, "external_id": c.external_id, "company": c.company, "product": c.product,
            "issue": c.issue, "state": c.state, "status": c.status, "assigned_to": c.assigned_to,
            "received_at": c.received_at.isoformat(), **deadlines(c),
            "governing": governing(a), "stage": a.stage if a else None,
            "scope_out": bool(a and a.scope and a.scope.get("out_of_scope")),
            "n_sentences": len(d.sentences) if d else None, "n_flagged": flagged,
            "snippet": c.narrative[:220]}


def analysis_json(a: Analysis) -> dict:
    return {"id": a.id, "origin": a.origin, "stage": a.stage, "force_draft": a.force_draft, "error": a.error,
            "classification": a.classification, "retrieval": a.retrieval, "scope": a.scope, "draft": a.draft,
            "checks": a.checks, "generator_model": a.generator_model, "verifier": a.verifier,
            "nli_cutoff": a.nli_cutoff, "timings_ms": a.timings_ms,
            "created_at": a.created_at.isoformat(), "finished_at": a.finished_at.isoformat() if a.finished_at else None}


def detail(c: Case) -> dict:
    a, _ = latest(c)
    return {**summary(c), "narrative": c.narrative, "sub_product": c.sub_product,
            "cfpb_date_received": c.cfpb_date_received, "source": c.source,
            "decision_note": c.decision_note, "decided_by": c.decided_by,
            "decided_at": c.decided_at.isoformat() if c.decided_at else None,
            "analysis": analysis_json(a) if a else None,
            "history": [{"id": x.id, "origin": x.origin, "stage": x.stage, "created_at": x.created_at.isoformat()}
                        for x in c.analyses],
            "drafts": [{"id": d.id, "version": d.version, "author": d.author, "note": d.note,
                        "created_at": d.created_at.isoformat(), "sentences": d.sentences} for d in c.drafts],
            "events": [{"at": e.at.isoformat(), "actor": e.actor, "kind": e.kind, "detail": e.detail}
                       for e in reversed(c.events)]}


def load_case(s, case_id: int) -> Case:
    # populate_existing: after a write in the same session, reload the collections instead of
    # returning the copies already in the session (which would miss the new draft or event).
    c = s.get(Case, case_id, options=[selectinload(Case.analyses), selectinload(Case.drafts),
                                      selectinload(Case.events)], populate_existing=True)
    if not c:
        raise HTTPException(404, "No such case.")
    return c


def start_analysis(s, c: Case, actor: str, force_draft: bool = False) -> None:
    if c.status == "analyzing":
        raise HTTPException(409, "An analysis is already running for this case.")
    a = Analysis(case_id=c.id, origin="live", stage="queued", force_draft=force_draft)
    s.add(a)
    c.status = "analyzing"
    log_event(s, c, actor, "analysis_started", "Draft requested despite the scope flag." if force_draft else None)
    s.commit()
    eng.enqueue(a.id)


# ------------------------------------------------------------------ models
class NewCase(BaseModel):
    narrative: str = Field(min_length=20, max_length=20000)
    company: str | None = Field(None, max_length=200)
    product: str | None = Field(None, max_length=200)
    issue: str | None = Field(None, max_length=300)
    state: str | None = Field(None, max_length=8)
    analyze: bool = True


class AnalyzeRequest(BaseModel):
    force_draft: bool = False


class SentenceIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    cited_chunk_ids: list[str] = []


class DraftIn(BaseModel):
    sentences: list[SentenceIn] = Field(min_length=1, max_length=40)
    note: str | None = Field(None, max_length=2000)


class Decision(BaseModel):
    action: str  # approve | refer | reopen
    note: str | None = Field(None, max_length=4000)
    override_flags: bool = False


class Comment(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class Assign(BaseModel):
    officer: str | None = Field(None, max_length=80)


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health():
    m = eng.MODELS
    return {"models": m.status, "error": m.error, "ready": m.ready.is_set() and not m.error,
            "database": "postgres" if config.DATABASE_URL.startswith("postgres") else "sqlite",
            "nli_cutoff": config.CHECK_CUTOFF, "checker": config.CHECKER, "live_drafting": config.HAS_NVIDIA_KEY,
            "generator_model": config.GENERATOR_MODEL}


@app.get("/api/cases")
def list_cases():
    with Session() as s:
        cases = s.query(Case).options(selectinload(Case.analyses), selectinload(Case.drafts)).all()
        return [summary(c) for c in cases]


@app.post("/api/cases", status_code=201)
def create_case(body: NewCase, x_officer: str | None = Header(None)):
    actor = officer(x_officer)
    with Session() as s:
        c = Case(source="intake", narrative=body.narrative.strip(), company=body.company, product=body.product,
                 issue=body.issue, state=body.state, received_at=now(), status="new", assigned_to=actor)
        s.add(c)
        s.flush()
        log_event(s, c, actor, "created", "Entered through intake.")
        s.commit()
        if body.analyze:
            start_analysis(s, load_case(s, c.id), actor)
        return {"id": c.id}


@app.get("/api/cases/{case_id}")
def get_case(case_id: int):
    with Session() as s:
        return detail(load_case(s, case_id))


@app.post("/api/cases/{case_id}/analyze")
def analyze(case_id: int, body: AnalyzeRequest, x_officer: str | None = Header(None)):
    with Session() as s:
        c = load_case(s, case_id)
        if c.status in ("approved", "referred"):
            raise HTTPException(409, "Reopen the case before running a new analysis.")
        start_analysis(s, c, officer(x_officer), body.force_draft)
        return detail(load_case(s, case_id))


@app.post("/api/cases/{case_id}/drafts")
def save_draft(case_id: int, body: DraftIn, x_officer: str | None = Header(None)):
    actor = officer(x_officer)
    with Session() as s:
        c = load_case(s, case_id)
        a, _ = latest(c)
        if not a or not a.retrieval or c.status not in ("in_review", "scope_review"):
            raise HTTPException(409, "Drafts can be edited only on a case under review.")
        texts = [x.text.strip() for x in body.sentences]
        context = eng.context_from(a.retrieval)
        known = {ch.chunk_id for ch in context}
        cited = [[cid for cid in x.cited_chunk_ids if cid in known] for x in body.sentences]
        checks = None
        if eng.MODELS.verifier is not None:
            checks = eng.MODELS.check(texts, cited, context)
        version = len(c.drafts) + 1
        s.add(DraftVersion(case_id=c.id, analysis_id=a.id, version=version, author=actor, note=body.note,
                           sentences=eng.draft_sentences(texts, cited, checks)))
        c.status = "in_review"
        n_flag = sum(ch["label"] == "unsupported" for ch in checks or [])
        log_event(s, c, actor, "edited",
                  f"Draft v{version}: {len(texts)} sentences, "
                  + (f"{n_flag} flagged." if checks is not None else "not re-checked (checker not loaded)."))
        s.commit()
        return detail(load_case(s, case_id))


@app.post("/api/cases/{case_id}/decision")
def decide(case_id: int, body: Decision, x_officer: str | None = Header(None)):
    actor = officer(x_officer)
    with Session() as s:
        c = load_case(s, case_id)
        _, d = latest(c)
        if body.action == "approve":
            if c.status != "in_review" or not d:
                raise HTTPException(409, "Only a case with a draft under review can be approved.")
            flagged = sum(x["label"] == "unsupported" for x in d.sentences)
            if flagged and not (body.override_flags and (body.note or "").strip()):
                raise HTTPException(422, f"{flagged} sentence(s) are flagged. Fix them, or approve with an "
                                         "override and a note explaining why.")
            c.status = "approved"
            detail_text = f"Approved draft v{d.version}." + (f" Override of {flagged} flag(s)." if flagged else "")
        elif body.action == "refer":
            if c.status in ("analyzing", "referred", "approved"):
                raise HTTPException(409, f"A case that is {c.status.replace('_', ' ')} cannot be referred.")
            if not (body.note or "").strip():
                raise HTTPException(422, "Say why the case is referred.")
            c.status = "referred"
            detail_text = "Referred for specialist review."
        elif body.action == "reopen":
            if c.status not in ("approved", "referred"):
                raise HTTPException(409, "Only approved or referred cases can be reopened.")
            c.status = "in_review" if d else ("scope_review" if c.analyses else "new")
            detail_text = "Reopened."
        else:
            raise HTTPException(422, "action must be approve, refer or reopen.")
        c.decision_note = body.note if body.action != "reopen" else None
        c.decided_by, c.decided_at = (actor, now()) if body.action != "reopen" else (None, None)
        log_event(s, c, actor, body.action, detail_text + (f" Note: {body.note.strip()}" if (body.note or "").strip() else ""))
        s.commit()
        return detail(load_case(s, case_id))


@app.post("/api/cases/{case_id}/comments")
def comment(case_id: int, body: Comment, x_officer: str | None = Header(None)):
    with Session() as s:
        c = load_case(s, case_id)
        log_event(s, c, officer(x_officer), "comment", body.text.strip())
        s.commit()
        return detail(load_case(s, case_id))


@app.post("/api/cases/{case_id}/assign")
def assign(case_id: int, body: Assign, x_officer: str | None = Header(None)):
    actor = officer(x_officer)
    with Session() as s:
        c = load_case(s, case_id)
        c.assigned_to = (body.officer or "").strip() or None
        log_event(s, c, actor, "assigned", f"Assigned to {c.assigned_to}." if c.assigned_to else "Unassigned.")
        s.commit()
        return detail(load_case(s, case_id))


@app.get("/api/stats")
def stats():
    with Session() as s:
        cases = s.query(Case).options(selectinload(Case.analyses), selectinload(Case.drafts)).all()
    rows = [summary(c) for c in cases]
    open_rows = [r for r in rows if r["status"] in OPEN]
    by_status, by_reg = {}, {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        reg = r["governing"]["regulation"] if r["governing"] else "Not analysed"
        by_reg[reg] = by_reg.get(reg, 0) + 1
    drafted = [r for r in rows if r["n_sentences"]]
    n_sent = sum(r["n_sentences"] for r in drafted)
    return {"total": len(rows), "open": len(open_rows), "by_status": by_status, "by_regulation": by_reg,
            "overdue": sum(r["days_left"] < 0 for r in open_rows),
            "due_soon": sum(0 <= r["days_left"] <= 3 for r in open_rows),
            "scope_flags": sum(r["scope_out"] for r in rows),
            "drafts": len(drafted), "sentences": n_sent,
            "flagged_sentences": sum(r["n_flagged"] or 0 for r in drafted)}


@app.get("/api/about")
def about():
    """What the models are and how well they did in the project's evaluation."""
    def read(name):
        p = config.ROOT / "results" / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    scope = eng.MODELS.scope.spec if eng.MODELS.scope else None
    final = read("final_results.json")  # scripts/build_final_results.py
    out = {"health": health(),
           "scope_model": scope and {"name": scope["name"], "threshold": scope["threshold"],
                                     "report_half": scope["report_half"], "source": scope["source"]},
           "retrieval": None, "checker": None, "classifier": None}
    if final:
        w = final["H1_retrieval"]["with_fcra"]["retrievers"]
        best = final["H1_retrieval"]["best_retriever"]["name"]
        s2 = final["H4_checker"]["set2"]
        out["retrieval"] = {"name": best, "n": w[best]["n"], "hit@1": w[best]["hit@1"], "hit@5": w[best]["hit@5"],
                            "bm25_hit@5": w["bm25"]["hit@5"]}
        post = final.get("post_h1_retrieval")
        if post and config.RETRIEVER == "llm":
            v2 = post["retrievers"]["llm_rerank"]
            out["retrieval"] |= {"name": "llm_rerank", "n": v2["n"], "hit@1": v2["hit@1"], "hit@5": v2["hit@5"],
                                 "h1_hit@1": w[best]["hit@1"], "h1_hit@5": w[best]["hit@5"]}
        rr = read("reranker_top1_section.json")
        if rr and config.RETRIEVER == "llm":
            key = "gpt" if config.RERANK_MODEL.startswith("codex:") else "super"
            out["reranker"] = {"model": config.RERANK_MODEL, **rr["rerankers"][key]["heldout"],
                               "super_top1": rr["rerankers"]["super"]["heldout"]["top1_correct"]}
        out["checker"] = {"n": s2["n"], "labels": s2["labels"], "at_T": s2["nli@T"], "at_0_5": s2["nli@0.5"]}
        ens = (read("checker_ultra_compare.json") or {}).get("nli_or_ultra_avg")
        if ens and config.CHECKER == "ensemble":  # EXPERIMENT_LOG E12b
            out["checker"]["ensemble"] = {"cut": ens["cut_set1"], "balanced_accuracy": ens["BA_set2_at_cut"],
                                          "unsupported_recall": ens["unsupported_recall_set2_at_cut"]}
        out["classifier"] = final["classifier"]
    return out


# ------------------------------------------------------------------ frontend
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = config.FRONTEND_DIST / path
        if path and f.is_file() and config.FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
