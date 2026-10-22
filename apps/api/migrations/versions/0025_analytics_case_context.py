"""Retain report context for private match-view inventory breakdowns."""
from alembic import op
import sqlalchemy as sa
revision="0025_analytics_context"
down_revision="0024_product_analytics"
branch_labels=depends_on=None


def upgrade():
    for table in ("product_events","product_daily"):
        op.add_column(table,sa.Column("case_id",sa.Uuid(),sa.ForeignKey("lost_cases.id",ondelete="SET NULL")))
        op.create_index("ix_"+table+"_case_id",table,["case_id"])


def downgrade():
    raise RuntimeError("Preserve measurement evidence; restore a verified backup for rollback.")
