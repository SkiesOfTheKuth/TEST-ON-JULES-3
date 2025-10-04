"""Initial tables for API keys and audit logs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20250101000000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("scopes", sa.String(length=255), nullable=False, server_default="calculate"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "request_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("expression_hash", sa.String(length=128), nullable=False),
        sa.Column("expression", sa.String(length=512), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "quotas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limit", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("quotas")
    op.drop_table("request_audit")
    op.drop_table("api_keys")
