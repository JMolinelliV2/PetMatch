"""Reversible prelaunch layer; normal User/Pet/Photo records remain unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "0023_prelaunch"
down_revision = "0022_visual_spaces"
branch_labels = depends_on = None


def upgrade():
    for column in (
        sa.Column("prelaunch_completed_at", sa.DateTime(timezone=True)),
        sa.Column("prelaunch_registered_at", sa.DateTime(timezone=True)),
        sa.Column("prelaunch_demo_stage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evaluation_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evaluation_consent_version", sa.String(40)),
        sa.Column("evaluation_consent_at", sa.DateTime(timezone=True)),
    ): op.add_column("pets", column)
    op.create_table("prelaunch_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("attribution", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_prelaunch_sessions_user_id", "prelaunch_sessions", ["user_id"])
    op.create_index("ix_prelaunch_sessions_created_at", "prelaunch_sessions", ["created_at"])
    op.create_table("early_access_leads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("name", sa.String(120)),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True),
        sa.Column("pet_id", sa.Uuid(), sa.ForeignKey("pets.id", ondelete="SET NULL")),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("prelaunch_sessions.id", ondelete="SET NULL")),
        sa.Column("attribution", sa.JSON(), nullable=False),
        *[sa.Column(name, sa.DateTime(timezone=True)) for name in ("requested_at", "confirmed_at", "waitlist_confirmed_at", "early_access_at", "unsubscribed_at", "offer_viewed_at", "confirmation_expires_at", "confirmation_requested_at", "mail_available_at")],
        sa.Column("price_variant", sa.Integer()), sa.Column("paid_intent", sa.Boolean()),
        sa.Column("payment_preference", sa.String(40)), sa.Column("survey", sa.JSON(), nullable=False),
        sa.Column("confirmation_hash", sa.String(64), unique=True), sa.Column("confirmation_encrypted", sa.String(512)),
        sa.Column("confirmation_mail_status", sa.String(24), nullable=False),
        sa.Column("welcome_mail_status", sa.String(24), nullable=False),
        sa.Column("mail_attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("price_variant IS NULL OR price_variant IN (390,690,990)", name="ck_early_access_price"))
    op.create_index("ix_early_access_leads_email", "early_access_leads", ["email"])
    op.create_table("prelaunch_events",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("name", sa.String(40), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("prelaunch_sessions.id", ondelete="SET NULL")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("pet_id", sa.Uuid(), sa.ForeignKey("pets.id", ondelete="SET NULL")),
        sa.Column("lead_id", sa.Uuid(), sa.ForeignKey("early_access_leads.id", ondelete="SET NULL")),
        sa.Column("deduplication_key", sa.String(160), nullable=False, unique=True),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    for field in ("name", "session_id", "user_id", "created_at"):
        op.create_index("ix_prelaunch_events_"+field, "prelaunch_events", [field])


def downgrade():
    raise RuntimeError("Disable PRELAUNCH_MODE instead; preserve profiles, consent and experiment evidence.")
