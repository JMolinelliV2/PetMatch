"""Opt-in real CPU/Redis/Postgres/S3 smoke. Creates and removes only disposable records."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import tempfile
from time import monotonic
import urllib.request
from uuid import uuid4
import psycopg
from psycopg import sql
from alembic import command
from alembic.config import Config
from rq import Queue
from rq.serializers import JSONSerializer
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.analysis import queue,tasks
from app.analysis.service import schedule_photo,schedule_text,utcnow
from app.analysis.worker import PersistentWorker
from app.core.config import settings
from app.core.image_storage import store_private_image,delete_private_image
from app.embeddings.backfill import backfill
from app.matching.engine import evaluate_observation
from app.matching.scoring import cosine
from app.models import User,Pet,LostCase,Observation,Photo,AnalysisJob,Embedding,FeatureSet,Match,Notification

FIXTURES={
    "dog": "https://upload.wikimedia.org/wikipedia/commons/c/c4/A_lovely_dog_sitting_on_floor.jpg",
    "cat": "https://upload.wikimedia.org/wikipedia/commons/7/71/Bangladeshi_Cat.jpg",
}


def fetch_fixtures(directory):
    directory.mkdir(parents=True,exist_ok=True)
    for species,url in FIXTURES.items():
        path=directory/(species+".jpg")
        if not path.is_file():
            request=urllib.request.Request(url,headers={"User-Agent":"MascoMatch/1.0 (technical smoke; info@mascomatch.com)"})
            with urllib.request.urlopen(request,timeout=60) as response:
                payload=response.read(settings.max_photo_size_bytes+1)
            from app.embeddings.cropper import decode_image
            decode_image(payload)
            path.write_bytes(payload)
    return directory


def run(directory):
    # Operator connection is needed to create a disposable DB; never migrate the application DB here.
    if settings.mail_delivery_mode!="disabled":
        raise ValueError("Smoke requires MAIL_DELIVERY_MODE=disabled")
    base=settings.database_url
    if not base.startswith("postgresql"):
        raise ValueError("Smoke requires PostgreSQL/PostGIS/pgvector")
    name="mascomatch_ai_smoke_"+uuid4().hex
    url=make_url(base).set(database=name).render_as_string(hide_password=False)
    control=psycopg.connect(base.replace("postgresql+psycopg://","postgresql://"),autocommit=True)
    real_connection=queue.get_queue().connection
    real_connection.ping()
    prefix="mascomatch-smoke-"+uuid4().hex
    queues={tier:Queue(prefix+"-"+tier,connection=real_connection,serializer=JSONSerializer) for tier in ("urgent","normal","backfill")}
    keys=[]
    db_engine=None
    created=False
    original_queue,original_factory,original_tasks=queue.get_queue,queue.SessionLocal,tasks.SessionLocal
    old_ai,old_embeddings=settings.ai_enabled,settings.embeddings_enabled
    report={"effective_identity_accuracy":None,"purpose":"technical smoke; repeated photos are not an identity evaluation", "checks":{}}
    try:
        control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)));created=True
        settings.database_url=url
        config=Config(str(Path(__file__).resolve().parents[2]/"alembic.ini"))
        config.set_main_option("script_location",str(Path(__file__).resolve().parents[2]/"migrations"))
        command.upgrade(config,"head")
        db_engine=create_engine(url)
        factory=sessionmaker(bind=db_engine,expire_on_commit=False)
        queue.SessionLocal=tasks.SessionLocal=factory
        queue.get_queue=lambda source="text",priority=50: queues["urgent" if priority>=90 else "normal" if priority>=50 else "backfill"]
        settings.ai_enabled=False;settings.embeddings_enabled=True
        ids=[]
        with factory() as db:
            user=User(email="smoke-owner@example.test",name="Synthetic",password_hash="not-a-login",email_verified_at=utcnow())
            db.add(user);db.flush()
            for species in ("dog","cat"):
                pet=Pet(owner_id=user.id,name="Synthetic",species=species,primary_color="brown",size="medium")
                db.add(pet);db.flush()
                case=LostCase(pet_id=pet.id,lost_at=utcnow(),latitude=-34.9,longitude=-56.1)
                obs=Observation(species=species,primary_color="brown",size="medium",description="",
                    observed_at=utcnow(),latitude=-34.9,longitude=-56.1)
                db.add_all([case,obs]);db.flush()
                payload=(directory/("dog.jpg" if species=="dog" else "cat.jpg")).read_bytes()
                for kind,owner in (("pet",pet),("observation",obs)):
                    key,width,height=store_private_image(kind,owner.id,"image/jpeg",payload);keys.append(key)
                    photo=Photo(owner_type=kind,owner_id=owner.id,storage_key=key,mime_type="image/jpeg",width=width,height=height)
                    db.add(photo);db.flush();schedule_photo(db,photo)
                ids.append((species,case.id,obs.id))
            db.commit()
        assert queue.dispatch_pending()==8
        assert queues["urgent"].count==8 and queues["backfill"].count==0
        worker=PersistentWorker(list(queues.values()),connection=real_connection,serializer=JSONSerializer,log_job_description=False)
        started=monotonic();worker.work(burst=True,logging_level="WARNING")
        report["visual_seconds"]=monotonic()-started
        report["checks"]["priority_queues"]=True
        with factory() as db:
            assert db.scalar(text("SELECT count(*) FROM embeddings"))==8
            assert all(j.status=="SUCCEEDED" for j in db.scalars(select(AnalysisJob)))
            report["visual_jobs"]=[{"provider":j.provider,"metrics":j.metrics} for j in db.scalars(select(AnalysisJob))]
            for species,case_id,obs_id in ids:
                vectors=list(db.scalars(select(Embedding).join(AnalysisJob).where(AnalysisJob.owner_id==obs_id)))
                assert len(vectors)==1 and vectors[0].dimension==512
                assert vectors[0].provider=="pet_reid"
                assert abs(cosine(vectors[0].vector,vectors[0].vector)-1)<1e-5
                evaluate_observation(db,obs_id)
                assert db.scalar(select(Match).where(Match.observation_id==obs_id)) is not None
                report["checks"][species]=True
            db.commit()
            report["checks"]["notification_outbox"]=db.scalar(select(Notification.id).limit(1)) is not None
            assert report["checks"]["notification_outbox"]
        assert backfill(factory)["created"]==0
        report["checks"]["idempotent_backfill"]=True
        settings.ai_enabled=True
        with factory() as db:
            obs=db.get(Observation,ids[0][2])
            obs.description="Perro marrón mediano con pecho blanco y collar rojo."
            text_job=schedule_text(db,"observation",obs.id)
            photo=db.scalar(select(Photo).where(Photo.owner_type=="observation",Photo.owner_id==obs.id))
            image_job=schedule_photo(db,photo)
            semantic_ids=[text_job.id,image_job.id];db.commit()
        assert queue.dispatch_pending()==2
        worker.work(burst=True,logging_level="WARNING")
        with factory() as db:
            for job_id in semantic_ids:
                job=db.get(AnalysisJob,job_id)
                assert job.status=="SUCCEEDED",job.error_code
                features=db.scalar(select(FeatureSet).where(FeatureSet.analysis_job_id==job_id))
                assert features.features["species"]["value"]=="dog"
                report["checks"][job.source_type+"_features"]=True
            report["checks"]["crop_reuse"]=db.get(AnalysisJob,semantic_ids[1]).metrics.get("crop_reused",False)
        report["worker_peak_rss_kib"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["checks"]["postgres_redis_storage"]=True
        report["checks"]["no_external_email"]=settings.mail_delivery_mode=="disabled"
        return report
    finally:
        settings.database_url=base
        settings.ai_enabled,settings.embeddings_enabled=old_ai,old_embeddings
        queue.get_queue,queue.SessionLocal,tasks.SessionLocal=original_queue,original_factory,original_tasks
        for item in queues.values():
            item.delete(delete_jobs=True)
        for key in keys:
            delete_private_image(key)
        if db_engine:
            db_engine.dispose()
        if created:
            control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        control.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-disposable-database",action="store_true",required=True)
    parser.add_argument("--fixtures",type=Path,default=Path("/tmp/mascomatch-smoke-photos"))
    parser.add_argument("--download-fixtures",action="store_true")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.download_fixtures:
        fetch_fixtures(args.fixtures)
    report=run(args.fixtures)
    result=json.dumps(report,indent=2)
    if args.output:
        args.output.write_text(result,encoding="utf-8")
    print(result)


if __name__=="__main__":
    main()
