"""SQLAlchemy models for the gateway service."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
