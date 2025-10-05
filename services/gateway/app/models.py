"""SQLAlchemy models for the gateway service."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator


class JSONBCompat(TypeDecorator):
    """Use PostgreSQL JSONB when available and fall back to generic JSON."""

    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[str] = mapped_column(String(255), default="calculate")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow)
    expires_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RequestAudit(Base):
    __tablename__ = "request_audit"
    __table_args__ = (
        Index("ix_request_audit_api_key_id_created_at", "api_key_id", "created_at"),
        Index("ix_request_audit_expression_hash", "expression_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    expression_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expression: Mapped[str] = mapped_column(String(512), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow)


class Quota(Base):
    __tablename__ = "quotas"
    __table_args__ = (
        Index("ix_quotas_api_key_window", "api_key_id", "window_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    window_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usage: Mapped[int] = mapped_column(Integer, default=0)
    limit: Mapped[int] = mapped_column(Integer, default=0)


class TenantPolicy(Base):
    __tablename__ = "tenant_policies"
    __table_args__ = (
        UniqueConstraint("tenant", name="uq_tenant_policies_tenant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(512))
    max_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allowed_queues: Mapped[list[str]] = mapped_column(JSONBCompat, nullable=False, default=list)
    max_runtime_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    banned_patterns: Mapped[list[str]] = mapped_column(JSONBCompat, nullable=False, default=list)
    allow_heavy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_gpu: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quota_limit: Mapped[Optional[int]] = mapped_column(Integer)
    quota_window_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
        nullable=False,
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_created_at", "created_at"),
        Index("ix_jobs_priority", "priority"),
        Index("ix_jobs_queue_name", "queue_name"),
        Index("ix_jobs_tenant", "tenant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False
    )
    started_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    input_expression: Mapped[str] = mapped_column(String(512), nullable=False)
    context: Mapped[Dict[str, Any]] = mapped_column(JSONBCompat, default=dict, nullable=False)
    result_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBCompat)
    error: Mapped[Optional[str]] = mapped_column(Text)
    requested_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list[str]] = mapped_column(JSONBCompat, default=list, nullable=False)
    queue_name: Mapped[str] = mapped_column(String(128), nullable=False, default="calculator-jobs")
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    policy_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBCompat, default=dict, nullable=False)
    policy_violations: Mapped[list[str]] = mapped_column(JSONBCompat, default=list, nullable=False)
    policy_enforced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_runtime_ms: Mapped[Optional[int]] = mapped_column(Integer)

