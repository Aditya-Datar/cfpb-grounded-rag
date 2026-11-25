"""Database tables for the officer app (SQLAlchemy 2.0).

Postgres (Neon) in production, with every table in its own schema (config.SCHEMA)
so the app never touches anything else in the database. SQLite works locally
when DATABASE_URL is unset.

    cases      one consumer complaint and its review state
    analyses   one pipeline run on a case (classification, retrieval, scope, draft, checks)
    drafts     officer-edited versions of the draft, each re-checked sentence by sentence
    events     audit trail: who did what, when
"""
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine,
                        event, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.backend.config import DATABASE_URL, SCHEMA

IS_PG = DATABASE_URL.startswith("postgres")
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _url(url: str) -> str:
    return url.replace("postgres://", "postgresql+psycopg://", 1).replace(
        "postgresql://", "postgresql+psycopg://", 1) if IS_PG else url


engine = create_engine(
    _url(DATABASE_URL), pool_pre_ping=True, pool_recycle=300,
    # Neon's pooled endpoint (PgBouncer) does not keep prepared statements.
    connect_args={"prepare_threshold": None} if IS_PG else {"check_same_thread": False},
)
if IS_PG:
    @event.listens_for(engine, "connect")
    def _search_path(dbapi_conn, _):
        with dbapi_conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{SCHEMA}"')
        dbapi_conn.commit()

Session = sessionmaker(engine, expire_on_commit=False)


def now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend. SQLite drops the offset on the way in, so naive
    values read back are UTC; without this, deadline arithmetic against now() fails on SQLite."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return value.astimezone(timezone.utc) if value is not None and value.tzinfo else value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(32), unique=True)  # CFPB complaint id
    source: Mapped[str] = mapped_column(String(32))          # cfpb_gold | intake
    narrative: Mapped[str] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(String(200))
    product: Mapped[str | None] = mapped_column(String(200))  # as filed by the consumer
    sub_product: Mapped[str | None] = mapped_column(String(200))
    issue: Mapped[str | None] = mapped_column(String(300))
    state: Mapped[str | None] = mapped_column(String(8))
    cfpb_date_received: Mapped[str | None] = mapped_column(String(16))
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    # new -> analyzing -> in_review | scope_review -> approved | referred ; failed on errors
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(80))
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(80))
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now, onupdate=now)

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="case", order_by="Analysis.id",
                                                      cascade="all, delete-orphan")
    drafts: Mapped[list["DraftVersion"]] = relationship(back_populates="case", order_by="DraftVersion.version",
                                                        cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="case", order_by="Event.id",
                                                 cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    origin: Mapped[str] = mapped_column(String(64))           # live | replay:<run folder>
    stage: Mapped[str] = mapped_column(String(24), default="queued")  # queued classify retrieve scope generate verify done failed
    force_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    narrative_clean: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[dict | None] = mapped_column(JSONType)
    retrieval: Mapped[dict | None] = mapped_column(JSONType)
    scope: Mapped[dict | None] = mapped_column(JSONType)
    draft: Mapped[dict | None] = mapped_column(JSONType)
    checks: Mapped[list | None] = mapped_column(JSONType)
    generator_model: Mapped[str | None] = mapped_column(String(120))
    verifier: Mapped[str | None] = mapped_column(String(160))
    nli_cutoff: Mapped[float | None] = mapped_column(Float)
    timings_ms: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    case: Mapped[Case] = relationship(back_populates="analyses")


class DraftVersion(Base):
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer)
    sentences: Mapped[list] = mapped_column(JSONType)  # [{text, cited_chunk_ids, entail_prob, label}]
    author: Mapped[str] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)

    case: Mapped[Case] = relationship(back_populates="drafts")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    actor: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(Text)

    case: Mapped[Case] = relationship(back_populates="events")


def init_db() -> None:
    if IS_PG:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    else:
        from pathlib import Path
        Path(DATABASE_URL.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def log_event(session, case: Case, actor: str, kind: str, detail: str | None = None) -> None:
    session.add(Event(case_id=case.id, actor=actor, kind=kind, detail=detail))
