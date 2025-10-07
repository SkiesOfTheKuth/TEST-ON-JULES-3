"""Add symbolic engine cache table."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251201000003"
down_revision = "20251006000002_phase2_policy_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbolic_cache",
        sa.Column("expression_hash", sa.String(length=128), primary_key=True),
        sa.Column("canonical_form", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_symbolic_cache_created_at", "symbolic_cache", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_symbolic_cache_created_at", table_name="symbolic_cache")
    op.drop_table("symbolic_cache")
