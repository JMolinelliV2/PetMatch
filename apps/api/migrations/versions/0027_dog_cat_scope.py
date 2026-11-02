"""Restrict new publications to dogs/cats and retire unsupported processing.

Keep historical publications, original species, photos and completed evidence.
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_dog_cat_scope"
down_revision = "0026_analytics_rollup"
branch_labels = depends_on = None


def upgrade():
    pets = sa.table("pets", sa.column("id"), sa.column("species"))
    cases = sa.table("lost_cases", sa.column("id"), sa.column("pet_id"))
    observations = sa.table("observations", sa.column("id"), sa.column("species"),
                            sa.column("linked_case_id"), sa.column("matching_status"))
    bad_pets = sa.select(pets.c.id).where(pets.c.species.not_in(("dog", "cat")))
    bad_cases = sa.select(cases.c.id).where(cases.c.pet_id.in_(bad_pets))
    bad_observations = sa.select(observations.c.id).where(sa.or_(
        observations.c.species.not_in(("dog", "cat")), observations.c.linked_case_id.in_(bad_cases)))

    jobs = sa.table("analysis_jobs", *[sa.column(name) for name in (
        "owner_type", "owner_id", "status", "error_code", "finished_at", "lease_expires_at", "run_token", "dispatch_generation")])
    unsupported_owner = sa.or_(
        sa.and_(jobs.c.owner_type == "pet", jobs.c.owner_id.in_(bad_pets)),
        sa.and_(jobs.c.owner_type == "lost_case", jobs.c.owner_id.in_(bad_cases)),
        sa.and_(jobs.c.owner_type == "observation", jobs.c.owner_id.in_(bad_observations)))
    op.execute(jobs.update().where(unsupported_owner, jobs.c.status.in_(
        ("PENDING", "DISPATCHING", "QUEUED", "RUNNING"))).values(
        status="STALE", error_code="UNSUPPORTED_SPECIES", finished_at=sa.func.now(),
        lease_expires_at=None, run_token=None, dispatch_generation=jobs.c.dispatch_generation + 1))
    op.execute(observations.update().where(observations.c.id.in_(bad_observations)).values(matching_status="INACTIVE"))

    for name in ("matches", "notifications"):
        table = sa.table(name, sa.column("lost_case_id"), sa.column("observation_id"),
                         sa.column("is_active"), sa.column("email_status"))
        scope = sa.or_(table.c.lost_case_id.in_(bad_cases), table.c.observation_id.in_(bad_observations))
        op.execute(table.update().where(scope).values(is_active=False))
        if name == "notifications":
            op.execute(table.update().where(scope, table.c.email_status == "PENDING").values(email_status="CANCELLED"))
    reminders = sa.table("photo_reminders", sa.column("lost_case_id"), sa.column("status"))
    op.execute(reminders.update().where(reminders.c.lost_case_id.in_(bad_cases), reminders.c.status == "PENDING").values(status="CANCELLED"))

    # A CHECK (even NOT VALID) would reject unrelated updates to legacy records.
    # Validate only new rows or explicit changes to species / reactivation.
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""CREATE FUNCTION enforce_dog_cat_species() RETURNS trigger AS $$
        BEGIN
            IF NEW.species IS NULL OR NEW.species NOT IN ('dog', 'cat') THEN
                RAISE EXCEPTION 'MascoMatch supports only dogs and cats' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
        for table in ("pets", "observations"):
            op.execute(f"CREATE TRIGGER dog_cat_species BEFORE INSERT OR UPDATE OF species ON {table} FOR EACH ROW EXECUTE FUNCTION enforce_dog_cat_species()")
        op.execute("""CREATE FUNCTION enforce_dog_cat_case() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' OR NEW.pet_id IS DISTINCT FROM OLD.pet_id
               OR (NEW.status = 'ACTIVE' AND NEW.status IS DISTINCT FROM OLD.status) THEN
                IF NOT EXISTS (SELECT 1 FROM pets WHERE id = NEW.pet_id AND species IN ('dog', 'cat')) THEN
                    RAISE EXCEPTION 'MascoMatch supports only dogs and cats' USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
        op.execute("CREATE TRIGGER dog_cat_case BEFORE INSERT OR UPDATE OF pet_id, status ON lost_cases FOR EACH ROW EXECUTE FUNCTION enforce_dog_cat_case()")
    elif dialect == "sqlite":
        for table in ("pets", "observations"):
            for event, suffix in (("INSERT", "insert"), ("UPDATE OF species", "update")):
                op.execute(f"""CREATE TRIGGER {table}_dog_cat_{suffix} BEFORE {event} ON {table}
                    WHEN NEW.species IS NULL OR NEW.species NOT IN ('dog', 'cat')
                    BEGIN SELECT RAISE(ABORT, 'MascoMatch supports only dogs and cats'); END""")
        for event, suffix, condition in (
            ("INSERT", "insert", "1"),
            ("UPDATE OF pet_id, status", "update", "NEW.pet_id IS NOT OLD.pet_id OR (NEW.status = 'ACTIVE' AND NEW.status IS NOT OLD.status)"),
        ):
            op.execute(f"""CREATE TRIGGER cases_dog_cat_{suffix} BEFORE {event} ON lost_cases
                WHEN ({condition}) AND NOT EXISTS (SELECT 1 FROM pets WHERE id = NEW.pet_id AND species IN ('dog', 'cat'))
                BEGIN SELECT RAISE(ABORT, 'MascoMatch supports only dogs and cats'); END""")


def downgrade():
    # Never reactivate old jobs/alerts automatically: they may already be obsolete.
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in ("pets", "observations"):
            op.execute(f"DROP TRIGGER dog_cat_species ON {table}")
        op.execute("DROP TRIGGER dog_cat_case ON lost_cases")
        op.execute("DROP FUNCTION enforce_dog_cat_species()")
        op.execute("DROP FUNCTION enforce_dog_cat_case()")
    elif dialect == "sqlite":
        for table in ("pets", "observations", "cases"):
            for suffix in ("insert", "update"):
                op.execute(f"DROP TRIGGER {table}_dog_cat_{suffix}")
