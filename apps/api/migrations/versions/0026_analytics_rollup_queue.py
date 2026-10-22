"""Retry secondary aggregates independently of authoritative product facts."""
from alembic import op
import sqlalchemy as sa
revision="0026_analytics_rollup"
down_revision="0025_analytics_context"
branch_labels=depends_on=None


def upgrade():
    # Existing facts were aggregated transactionally; never replay them as new counts.
    op.add_column("product_events",sa.Column("aggregated",sa.Boolean(),nullable=False,server_default=sa.true()))
    op.alter_column("product_events","aggregated",server_default=sa.false())
    op.create_index("ix_product_events_aggregated","product_events",["aggregated"])


def downgrade():
    raise RuntimeError("Preserve pending aggregate evidence; restore a verified backup for rollback.")
