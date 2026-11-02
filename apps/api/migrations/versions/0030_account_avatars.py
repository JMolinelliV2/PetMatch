"""Optional private profile photos, kept outside animal analysis."""
from alembic import op
import sqlalchemy as sa

revision = "0030_account_avatars"
down_revision = "0029_description_format"
branch_labels = depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar_storage_key", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("avatar_version", sa.Uuid(), nullable=True))


def downgrade():
    op.drop_column("users", "avatar_version")
    op.drop_column("users", "avatar_storage_key")
