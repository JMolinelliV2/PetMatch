"""One-time Mercado Pago contributions and durable webhook reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "0031_donations"
down_revision = "0030_account_avatars"
branch_labels = depends_on = None


def upgrade():
    op.create_table("donations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("browser_key_hash", sa.String(64), nullable=False),
        sa.Column("amount_uyu", sa.BigInteger(), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("collector_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("public_base_url", sa.String(512), nullable=False),
        sa.Column("provider_order_id", sa.String(64), unique=True),
        sa.Column("checkout_url", sa.String(2048)),
        sa.Column("provider_status", sa.String(64)),
        sa.Column("provider_status_detail", sa.String(80)),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_uyu >= 1 AND amount_uyu <= 9007199254740991", name="ck_donation_amount"))
    op.create_index("ix_donations_environment", "donations", ["environment"])
    op.create_index("ix_donations_status", "donations", ["status"])
    op.create_table("donation_sync",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("provider_order_id", sa.String(64), nullable=False),
        sa.Column("pending", sa.Boolean(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(64)),
        sa.UniqueConstraint("environment", "provider_order_id", name="uq_donation_sync_resource"))
    op.create_index("ix_donation_sync_available_at", "donation_sync", ["available_at"])


def downgrade():
    op.drop_table("donation_sync")
    op.drop_table("donations")
