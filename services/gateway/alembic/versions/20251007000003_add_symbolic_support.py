"""Add symbolic job support"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251007000003"
down_revision = "20251006000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_policies",
        sa.Column("allow_symbolic", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("tenant_policies", "allow_symbolic", server_default=None)

    op.add_column(
        "jobs",
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="arithmetic"),
    )
    op.add_column("jobs", sa.Column("symbolic_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("jobs", sa.Column("symbolic_cache_key", sa.String(length=128), nullable=True))
    op.add_column("jobs", sa.Column("verification_passed", sa.Boolean(), nullable=True))
    op.add_column("jobs", sa.Column("verification_error", sa.String(length=255), nullable=True))
    op.alter_column("jobs", "mode", server_default=None)

    op.create_table(
        "symbolic_cache_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("expression_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("verification_passed", sa.Boolean(), nullable=True),
        sa.Column("verification_error", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_symbolic_cache_expression_hash",
        "symbolic_cache_entries",
        ["expression_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_symbolic_cache_expression_hash", table_name="symbolic_cache_entries")
    op.drop_table("symbolic_cache_entries")

    op.drop_column("jobs", "verification_error")
    op.drop_column("jobs", "verification_passed")
    op.drop_column("jobs", "symbolic_cache_key")
    op.drop_column("jobs", "symbolic_payload")
    op.drop_column("jobs", "mode")

    op.drop_column("tenant_policies", "allow_symbolic")
