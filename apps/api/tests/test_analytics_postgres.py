"""Concurrency on a separate, explicitly disposable PostgreSQL database; no models required."""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
from sqlalchemy import create_engine,func,select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config
from pathlib import Path
from datetime import timedelta
from app.core.config import settings
from app.analysis.service import utcnow
from app.models import (User,Pet,LostCase,Photo,ProductEvent,ProductDaily,RecoveryOutcome,
                        AnalyticsVisitor,AnalyticsSession,Observation,Match,MatchExposure)
from app.product_analytics import cleanup,record,photo_milestones
from app.photo_reminders import lock_photo_cases
from app.recovery import recover


@pytest.mark.skipif(os.getenv("RUN_VISUAL_MIGRATION_TESTS")!="1",reason="Requires explicitly disposable PostgreSQL")
def test_atomic_milestones_photos_and_recovery_with_multiple_workers(monkeypatch):
    assert os.getenv("DISPOSABLE_STACK")=="mascomatch-ai-upgrade"
    base=os.environ["MIGRATION_TEST_DATABASE_URL"]
    name="mascomatch_analytics_concurrency_"+uuid4().hex
    control=psycopg.connect(base.replace("postgresql+psycopg://","postgresql://"),autocommit=True)
    control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url=make_url(base).set(database=name).render_as_string(hide_password=False)
    monkeypatch.setattr(settings,"database_url",url)
    root=Path(__file__).resolve().parents[1]
    config=Config(str(root/"alembic.ini"));config.set_main_option("script_location",str(root/"migrations"))
    engine=create_engine(url);factory=sessionmaker(bind=engine,autoflush=False)
    try:
        command.upgrade(config,"head")
        with factory() as db:
            user=User(email="concurrency@example.test",name="Synthetic",password_hash="unused");db.add(user);db.flush()
            pet=Pet(name="Synthetic",species="dog",owner_id=user.id);db.add(pet);db.flush()
            case=LostCase(pet_id=pet.id,lost_at=utcnow());db.add(case);db.commit()
            uid,pid,cid=user.id,pet.id,case.id
        def milestone(_):
            with factory() as db:
                record(db,"account_created",uid,user=db.get(User,uid));db.commit()
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(milestone,range(16)))
        def upload(index):
            with factory() as db:
                lock_photo_cases(db,"pet",pid)
                photo=Photo(owner_type="pet",owner_id=pid,storage_key=f"synthetic-{index}.jpg",mime_type="image/jpeg")
                db.add(photo);db.flush();photo_milestones(db,photo,db.get(User,uid));db.commit()
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(upload,range(5)))
        def recovered(_):
            with factory() as db:
                case=db.scalar(select(LostCase).where(LostCase.id==cid).with_for_update())
                recover(db,case,db.get(User,uid));db.commit()
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(recovered,range(8)))
        with factory() as db:
            for event in ("account_created","first_photo_uploaded","three_photos_uploaded","five_photos_uploaded","recovery"):
                assert db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.name==event))==1
                assert db.scalar(select(func.sum(ProductDaily.count)).where(ProductDaily.name==event))==1
            assert db.scalar(select(func.count()).select_from(RecoveryOutcome))==1
        # Exercise every dashboard query with PostgreSQL's actual date/JSON dialect,
        # over both precise recent events and retained daily aggregates.
        from fastapi import Response
        from app.routers.admin_analytics import dashboard
        with factory() as db:
            for section in ("growth","usage","matching","impact","inventory"):
                for group in ("day","week","month"):
                    for days in (0,30):
                        data=dashboard(section=section,response=Response(),days=days,from_at=None,to_at=None,group=group,
                            source="all",provider="all",model=None,revision=None,job_source="all",job_provider="all",
                            job_model=None,job_revision=None,export_csv=False,country=None,department=None,locality=None,
                            db=db,user=db.get(User,uid))
                        assert data["section"]==section and data["analytics_started_at"]
                        if section=="growth":
                            assert next(step["people"] for step in data["funnel"] if step["event"]=="account_created")==1
        # Expiry and account deletion share FK paths; neither may block the other indefinitely.
        old=utcnow()-timedelta(days=200)
        with factory() as db:
            visitor=AnalyticsVisitor(id="a"*64,first_seen_at=old,last_seen_at=old);db.add(visitor);db.flush()
            session=AnalyticsSession(visitor_id=visitor.id,user_id=uid,started_at=old,last_seen_at=old,returning=False)
            observation=Observation(species="dog",description="Synthetic",observed_at=old)
            db.add_all([session,observation]);db.flush()
            match=Match(lost_case_id=cid,observation_id=observation.id,feature_score=.8,geo_score=.8,temporal_score=.8,
                        final_score=.8,evidence_coverage=.8,distance_meters=100,explanation=[])
            db.add(match);db.flush()
            db.add(MatchExposure(session_id=session.id,match_id=match.id,context="LOST_CASE",rank=1,shown_at=old,viewed_at=old))
            db.query(ProductEvent).update({"created_at":old})
            db.query(ProductDaily).update({"day":(utcnow()-timedelta(days=800)).date()});db.commit()
        def remove_account():
            from app.account_management import delete_account,lock_active_user
            with factory() as db:delete_account(db,lock_active_user(db,db.get(User,uid)))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(cleanup,factory),pool.submit(remove_account)]
            for future in futures:future.result(timeout=30)
        cleanup(factory)
        with factory() as db:
            assert db.get(User,uid) is None
            assert not db.scalar(select(ProductEvent)) and not db.scalar(select(MatchExposure))
    finally:
        engine.dispose()
        assert name.startswith("mascomatch_analytics_concurrency_")
        control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)));control.close()
