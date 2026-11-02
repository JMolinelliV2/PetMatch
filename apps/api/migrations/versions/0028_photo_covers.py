"""Per-publication thumbnail selection, preserving all existing photos."""
from alembic import op
import sqlalchemy as sa

revision = "0028_photo_covers"
down_revision = "0027_dog_cat_scope"
branch_labels = depends_on = None


def upgrade():
    op.create_table("photo_covers",
        sa.Column("owner_type", sa.String(24), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("photo_id", sa.Uuid(), sa.ForeignKey("photos.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("owner_type", "owner_id"))
    op.create_index("ix_photo_covers_photo_id", "photo_covers", ["photo_id"])


def downgrade():
    op.drop_index("ix_photo_covers_photo_id", table_name="photo_covers")
    op.drop_table("photo_covers")
