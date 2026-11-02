"""Track authored descriptions separately from legacy composed/system text."""
from alembic import op
import sqlalchemy as sa

revision = "0029_description_format"
down_revision = "0028_photo_covers"
branch_labels = depends_on = None


def upgrade():
    for table in ("lost_cases", "observations"):
        op.add_column(table, sa.Column("description_format", sa.String(16), nullable=False, server_default="LEGACY"))
        op.alter_column(table, "description_format", server_default="USER_TEXT")


def downgrade():
    for table in ("observations", "lost_cases"):
        op.drop_column(table, "description_format")
