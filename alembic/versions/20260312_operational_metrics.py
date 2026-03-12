"""Add persisted operational metric events for M8 observability.

Revision ID: 20260312_operational_metrics
Revises: 20260312_summary_ai_enrichments
Create Date: 2026-03-12 15:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260312_operational_metrics"
down_revision = "20260312_summary_ai_enrichments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_metric_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_name", sa.String(), nullable=False),
        sa.Column("metric_source", sa.String(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_metric_events_name_recorded_at",
        "operational_metric_events",
        ["metric_name", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_operational_metric_events_source_recorded_at",
        "operational_metric_events",
        ["metric_source", "recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_metric_events_source_recorded_at",
        table_name="operational_metric_events",
    )
    op.drop_index(
        "ix_operational_metric_events_name_recorded_at",
        table_name="operational_metric_events",
    )
    op.drop_table("operational_metric_events")
