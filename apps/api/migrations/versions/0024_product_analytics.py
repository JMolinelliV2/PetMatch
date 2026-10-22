"""First-party product facts, visibility and owner recovery attribution; additive only."""
from alembic import op
import sqlalchemy as sa

revision="0024_product_analytics"
down_revision="0023_prelaunch"  # Already applied locally: immutable historical schema, no runtime mode.
branch_labels=depends_on=None


def upgrade():
    for table in ("lost_cases","observations"):
        op.add_column(table,sa.Column("analytics_geo",sa.JSON(),nullable=False,server_default="{}"))
    for name,type_ in (("first_shown_at",sa.DateTime(timezone=True)),("first_viewed_at",sa.DateTime(timezone=True)),
                       ("first_viewed_rank",sa.Integer()),("best_viewed_rank",sa.Integer()),("viewed_snapshot",sa.JSON())):
        op.add_column("matches",sa.Column(name,type_))
    op.create_index("ix_matches_first_viewed_at","matches",["first_viewed_at"])
    op.add_column("match_feedback_events",sa.Column("context_snapshot",sa.JSON(),nullable=False,server_default="{}"))
    op.create_table("analytics_tracking",sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("started_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.CheckConstraint("id = 1",name="ck_single_analytics_tracking"))
    op.execute(sa.text("INSERT INTO analytics_tracking(id) VALUES (1)"))
    op.create_table("analytics_visitors",sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("first_seen_at",sa.DateTime(timezone=True),nullable=False),sa.Column("last_seen_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_analytics_visitors_last_seen_at","analytics_visitors",["last_seen_at"])
    op.create_table("analytics_sessions",sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("visitor_id",sa.String(64),sa.ForeignKey("analytics_visitors.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL")),
        sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("last_seen_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("is_returning",sa.Boolean(),nullable=False))
    for name in ("visitor_id","last_seen_at"):op.create_index("ix_analytics_sessions_"+name,"analytics_sessions",[name])
    op.create_table("product_events",sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("deduplication_key",sa.String(64),unique=True,nullable=False),sa.Column("name",sa.String(40),nullable=False),
        sa.Column("page",sa.String(24),nullable=False),sa.Column("visitor_id",sa.String(64)),sa.Column("session_id",sa.Uuid()),
        sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("actor_key",sa.String(64),nullable=False),
        sa.Column("country",sa.String(2),nullable=False),sa.Column("department",sa.String(80),nullable=False),sa.Column("locality",sa.String(80),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    for name in ("name","visitor_id","user_id","created_at"):op.create_index("ix_product_events_"+name,"product_events",[name])
    op.create_table("product_milestones",sa.Column("key",sa.String(64),primary_key=True),
        sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE")))
    op.create_table("product_daily",sa.Column("key",sa.String(64),primary_key=True),sa.Column("day",sa.Date(),nullable=False),
        *[sa.Column(name,sa.String(size),nullable=False) for name,size in (("name",40),("page",24),("visitor_id",64),
            ("session_key",64),("actor_key",64),("country",2),("department",80),("locality",80))],sa.Column("count",sa.Integer(),nullable=False))
    op.create_index("ix_product_daily_day_name","product_daily",["day","name"])
    op.create_index("ix_product_daily_geo_day","product_daily",["country","department","locality","day"])
    op.create_table("match_exposures",sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("session_id",sa.Uuid(),sa.ForeignKey("analytics_sessions.id",ondelete="CASCADE"),nullable=False),
        sa.Column("match_id",sa.Uuid(),sa.ForeignKey("matches.id",ondelete="CASCADE"),nullable=False),
        sa.Column("context",sa.String(24),nullable=False),sa.Column("rank",sa.Integer(),nullable=False),
        sa.Column("shown_at",sa.DateTime(timezone=True),nullable=False),sa.Column("viewed_at",sa.DateTime(timezone=True)),
        sa.UniqueConstraint("session_id","match_id","context",name="uq_match_exposure"))
    op.create_index("ix_match_exposures_match_id","match_exposures",["match_id"])
    op.create_table("recovery_outcomes",sa.Column("lost_case_id",sa.Uuid(),sa.ForeignKey("lost_cases.id",ondelete="CASCADE"),primary_key=True),
        sa.Column("owner_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("reason",sa.String(32),nullable=False),
        sa.Column("match_id",sa.Uuid(),sa.ForeignKey("matches.id",ondelete="SET NULL")),
        sa.Column("observation_id",sa.Uuid(),sa.ForeignKey("observations.id",ondelete="SET NULL")),
        sa.Column("recovered_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for name in ("reason","recovered_at"):op.create_index("ix_recovery_outcomes_"+name,"recovery_outcomes",[name])
    # Exact JSON filters without scanning every recommendation when segmenting models.
    if op.get_bind().dialect.name=="postgresql":
        op.execute("CREATE INDEX ix_match_analytics_visual ON matches ((recommendation_snapshot->>'visual_provider'), (recommendation_snapshot->'actual_visual_space'->>'model'), (recommendation_snapshot->'actual_visual_space'->>'revision'), recommended_at)")


def downgrade():
    raise RuntimeError("Restore a verified backup for rollback; analytics and recovery evidence must not be dropped automatically.")
