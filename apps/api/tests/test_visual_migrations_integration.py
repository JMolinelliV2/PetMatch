"""Real PostgreSQL upgrade tests; disposable databases only, explicitly enabled."""
import os
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
import psycopg
from psycopg import sql
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from app.core.config import settings


@pytest.mark.skipif(os.getenv("RUN_VISUAL_MIGRATION_TESTS")!="1",reason="Requires disposable PostgreSQL with pgvector/PostGIS")
def test_fresh_and_existing_postgres_preserve_historical_vectors(monkeypatch):
    base=os.environ["MIGRATION_TEST_DATABASE_URL"]
    assert os.environ.get("DISPOSABLE_STACK")=="mascomatch-ai-upgrade"
    control=psycopg.connect(base.replace("postgresql+psycopg://","postgresql://"),autocommit=True)
    root=Path(__file__).resolve().parents[1]
    cfg=Config(str(root/"alembic.ini"));cfg.set_main_option("script_location",str(root/"migrations"))
    try:
        for existing in (False,"0021_admin_operations","0022_visual_spaces","0023_prelaunch"):
            name="mascomatch_upgrade_"+uuid4().hex
            control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            url=make_url(base).set(database=name).render_as_string(hide_password=False)
            monkeypatch.setattr(settings,"database_url",url)
            engine=sa.create_engine(url)
            try:
                if existing:
                    command.upgrade(cfg,existing)
                    owner,photo,job=uuid4(),uuid4(),uuid4()
                    with engine.begin() as connection:
                        metadata=sa.MetaData()
                        photos=sa.Table("photos",metadata,autoload_with=connection)
                        jobs=sa.Table("analysis_jobs",metadata,autoload_with=connection)
                        connection.execute(photos.insert().values(id=photo,owner_type="observation",owner_id=owner,storage_key="historical.jpg",mime_type="image/jpeg"))
                        connection.execute(jobs.insert().values(id=job,deduplication_key="historic",owner_type="observation",owner_id=owner,photo_id=photo,
                            source_type="embedding",provider="open_clip",model="ViT-B-32:openai",prompt_version="old",input_hash="original",input_snapshot={},status="SUCCEEDED"))
                        connection.execute(sa.text("INSERT INTO embeddings (analysis_job_id,photo_id,model,dimension,input_hash,vector) VALUES (:j,:p,'ViT-B-32:openai',512,'original',CAST(:v AS vector))"),
                            {"j":job,"p":photo,"v":"[1,"+",".join(["0"]*511)+"]"})
                        def old_table(name):return sa.Table(name,metadata,autoload_with=connection,extend_existing=True)
                        now=datetime.now(timezone.utc);pet_id,case_id,obs_id,match_id,feedback_id,text_job=[uuid4() for _ in range(6)]
                        connection.execute(old_table("users").insert().values(id=owner,email="historical@example.test",name="Historical",password_hash="unused",notification_preferences={},status="ACTIVE"))
                        connection.execute(old_table("pets").insert().values(id=pet_id,owner_id=owner,name="Historical",species="dog",breed="unknown",sex="unknown",size="medium",primary_color="brown",secondary_colors=[],coat_type="unknown",distinctive_features=[]))
                        numbers=old_table("publication_numbers")
                        case_number=connection.execute(numbers.insert().returning(numbers.c.id)).scalar_one()
                        obs_number=connection.execute(numbers.insert().returning(numbers.c.id)).scalar_one()
                        connection.execute(old_table("lost_cases").insert().values(id=case_id,public_number=case_number,pet_id=pet_id,status="FOUND",lost_at=now,description="Historical",search_radius_meters=15000))
                        connection.execute(old_table("observations").insert().values(id=obs_id,public_number=obs_number,species="dog",description="Historical",observed_at=now,source_type="USER_SIGHTING",confidence=.5))
                        snapshot={"legacy":True,"marker":"preserve-this-snapshot"}
                        connection.execute(old_table("matches").insert().values(id=match_id,lost_case_id=case_id,observation_id=obs_id,
                            feature_score=.8,geo_score=.8,temporal_score=.8,final_score=.8,evidence_coverage=.8,distance_meters=100,
                            explanation=[],status="RESOLVED",is_active=False,feedback_at=now,recommended_at=now,
                            recommendation_source="GENERAL",recommended_score=.9,recommendation_snapshot=snapshot))
                        connection.execute(old_table("match_feedback_events").insert().values(id=feedback_id,match_id=match_id,actor_id=owner,status="RESOLVED",recovered=False,score=.9,legacy=True,created_at=now))
                        connection.execute(old_table("user_activity").insert().values(user_id=owner,occurred_at=now.replace(second=0,microsecond=0)))
                        tracking_start=connection.scalar(sa.text("SELECT started_at FROM operational_tracking WHERE id=1"))
                        connection.execute(jobs.insert().values(id=text_job,deduplication_key="historical-text",owner_type="observation",owner_id=obs_id,
                            source_type="text",provider="ollama",model="gemma3:4b",prompt_version="old",input_hash="old-text",input_snapshot={},status="SUCCEEDED"))
                        feature_data={"species":{"value":"dog","confidence":.9,"source":"text"}}
                        connection.execute(old_table("feature_sets").insert().values(id=uuid4(),analysis_job_id=text_job,features=feature_data))
                command.upgrade(cfg,"head")
                command.upgrade(cfg,"head")  # Safe repeated deploy.
                with engine.connect() as connection:
                    assert connection.scalar(sa.text("SELECT version_num FROM alembic_version"))=="0031_donations"
                    assert connection.scalar(sa.text("SELECT count(*) FROM analytics_tracking"))==1
                    assert {"product_events","product_daily","recovery_outcomes","match_exposures"}<=set(sa.inspect(connection).get_table_names())
                    assert {"vector","postgis"}<=set(connection.scalars(sa.text("SELECT extname FROM pg_extension")))
                    assert {"priority","preprocessing_version","metrics"}<=set(c["name"] for c in sa.inspect(connection).get_columns("analysis_jobs"))
                    if existing:
                        row=connection.execute(sa.text("SELECT provider,revision,space_id,input_hash,vector_dims(vector),vector::text FROM embeddings")).one()
                        expected="legacy"  # Rows inserted before/after the visual migration retain their defaults.
                        assert tuple(row[:5])==(expected,expected,expected,"original",512)
                        assert row[5].startswith("[1,0,0,")
                        assert connection.scalar(sa.text("SELECT priority FROM analysis_jobs WHERE deduplication_key='historic'"))==50
                        assert connection.scalar(sa.text("SELECT recommendation_snapshot FROM matches"))==snapshot
                        assert connection.scalar(sa.text("SELECT count(*) FROM match_feedback_events"))==1
                        assert connection.scalar(sa.text("SELECT count(*) FROM user_activity"))==1
                        assert connection.scalar(sa.text("SELECT started_at FROM operational_tracking WHERE id=1"))==tracking_start
                        assert connection.scalar(sa.text("SELECT features FROM feature_sets"))==feature_data
                        assert connection.scalar(sa.text("SELECT count(*) FROM recovery_outcomes"))==0
                        assert connection.scalar(sa.text("SELECT count(*) FROM product_events"))==0
            finally:
                engine.dispose()
                control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    finally:
        control.close()
