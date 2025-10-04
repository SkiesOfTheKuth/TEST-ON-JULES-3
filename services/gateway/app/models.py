"""SQLAlchemy models for the gateway service."""

"""Database models for the gateway service."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key_id: Mapped[int] = mapped_column(Integer, nullable=False)
    expression_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expression: Mapped[str] = mapped_column(String(512), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.utcnow)


class Quota(Base):
    __tablename__ = "quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key_id: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usage: Mapped[int] = mapped_column(Integer, default=0)
    limit: Mapped[int] = mapped_column(Integer, default=0)
