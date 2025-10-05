"""Add tenant policies table and job governance fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251006000002"
down_revision = "20250205000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    json_type = postgresql.JSONB(astext_type=sa.Text()) if dialect == "postgresql" else sa.JSON()

    if dialect == "postgresql":
        empty_list = sa.text("'[]'::jsonb")
        empty_object = sa.text("'{}'::jsonb")
    else:
        empty_list = sa.text("'[]'")
        empty_object = sa.text("'{}'")

    op.create_table(
        "tenant_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("max_priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("allowed_queues", json_type, nullable=False, server_default=empty_list),
        sa.Column("max_runtime_ms", sa.Integer(), nullable=False, server_default=sa.text("10000")),
        sa.Column("banned_patterns", json_type, nullable=False, server_default=empty_list),
        sa.Column("allow_heavy", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_gpu", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("quota_limit", sa.Integer(), nullable=True),
        sa.Column("quota_window_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant", name="uq_tenant_policies_tenant"),
    )

    job_table = "jobs"
    op.add_column(job_table, sa.Column("tenant", sa.String(length=255), nullable=False, server_default="default"))
    op.add_column(job_table, sa.Column("requested_priority", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column(job_table, sa.Column("queue_name", sa.String(length=128), nullable=False, server_default="calculator-jobs"))
    op.add_column(job_table, sa.Column("task_type", sa.String(length=32), nullable=False, server_default="standard"))
    op.add_column(job_table, sa.Column("policy_snapshot", json_type, nullable=False, server_default=empty_object))
    op.add_column(job_table, sa.Column("policy_violations", json_type, nullable=False, server_default=empty_list))
    op.add_column(job_table, sa.Column("policy_enforced", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column(job_table, sa.Column("estimated_runtime_ms", sa.Integer(), nullable=True))

    op.create_index("ix_jobs_queue_name", job_table, ["queue_name"])
    op.create_index("ix_jobs_tenant", job_table, ["tenant"])


def downgrade() -> None:
    job_table = "jobs"
    op.drop_index("ix_jobs_tenant", table_name=job_table)
    op.drop_index("ix_jobs_queue_name", table_name=job_table)
    op.drop_column(job_table, "estimated_runtime_ms")
    op.drop_column(job_table, "policy_enforced")
    op.drop_column(job_table, "policy_violations")
    op.drop_column(job_table, "policy_snapshot")
    op.drop_column(job_table, "task_type")
    op.drop_column(job_table, "queue_name")
    op.drop_column(job_table, "requested_priority")
    op.drop_column(job_table, "tenant")

    op.drop_table("tenant_policies")
