import asyncio
from datetime import timedelta
import logging

from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer
from sqlalchemy import select, update

from app.analysis.service import utcnow, is_current
from app.analysis.logging import log_event
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AnalysisJob

QUEUE_NAME = "mascomatch-analysis"


def queue_name(source="text",priority=50):
    kind="visual" if source=="embedding" else "semantic"
    tier="urgent" if priority>=90 else "normal" if priority>=50 else "backfill"
    return f"{QUEUE_NAME}-{kind}-{tier}"


def get_queue(source="text",priority=50) -> Queue:
    connection = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
    return Queue(queue_name(source,priority), connection=connection, serializer=JSONSerializer)


def dispatch_pending() -> int:
    if not (settings.ai_enabled or settings.embeddings_enabled):
        return 0
    now = utcnow()
    enabled_source = True if settings.ai_enabled and settings.embeddings_enabled else AnalysisJob.source_type != "embedding" if settings.ai_enabled else AnalysisJob.source_type == "embedding"
    with SessionLocal() as db:
        # Recover requests or workers interrupted between database and queue writes.
        expired = db.scalars(select(AnalysisJob).where(
            AnalysisJob.status.in_(["DISPATCHING", "QUEUED", "RUNNING"]),
            AnalysisJob.lease_expires_at <= now,
        ).with_for_update(skip_locked=True).limit(50))
        for job in expired:
            job.run_token = None
            job.lease_expires_at = None
            if job.attempts >= job.max_attempts:
                job.status, job.error_code, job.finished_at = "FAILED", "WORKER_INTERRUPTED", now
            else:
                job.status, job.available_at = "PENDING", now
        db.commit()
        ids = list(db.scalars(select(AnalysisJob.id).where(
            AnalysisJob.status == "PENDING", AnalysisJob.available_at <= now, enabled_source,
        ).order_by(AnalysisJob.priority.desc(),AnalysisJob.created_at).limit(20)))

    dispatched = 0
    for job_id in ids:
        with SessionLocal() as db:
            job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id).with_for_update())
            if job is None or job.status != "PENDING":
                continue
            if not is_current(db, job):
                job.status, job.error_code, job.finished_at = "STALE", "EVIDENCE_CHANGED", now
                job.lease_expires_at = job.run_token = None
                db.commit()
                continue
            job.status = "DISPATCHING"
            job.dispatch_generation += 1
            generation = job.dispatch_generation
            source,priority=job.source_type,job.priority
            job.lease_expires_at = now + timedelta(seconds=30)
            db.commit()
        try:
            queue=get_queue(source,priority)
            queue.enqueue(
                "app.analysis.tasks.process_analysis", str(job_id), generation,
                job_id=f"{job_id}-{generation}", unique=True,
                job_timeout=settings.timeout_for_source(source), result_ttl=3600, failure_ttl=86400,
            )
        except Exception:
            # A database outbox keeps reports and pending analysis when Redis is down.
            with SessionLocal() as db:
                db.execute(update(AnalysisJob).where(
                    AnalysisJob.id == job_id, AnalysisJob.status == "DISPATCHING",
                    AnalysisJob.dispatch_generation == generation,
                ).values(status="PENDING", available_at=now + timedelta(seconds=10), lease_expires_at=None, error_code="QUEUE_UNAVAILABLE"))
                db.commit()
            log_event("analysis_dispatch_failed", level=logging.WARNING, job_id=str(job_id), error_code="QUEUE_UNAVAILABLE")
            break
        with SessionLocal() as db:
            # Never overwrite a fast worker's RUNNING/SUCCEEDED state.
            db.execute(update(AnalysisJob).where(
                AnalysisJob.id == job_id, AnalysisJob.status == "DISPATCHING",
                AnalysisJob.dispatch_generation == generation,
            ).values(status="QUEUED", lease_expires_at=now + timedelta(seconds=settings.timeout_for_source(source) + 600), error_code=None))
            db.commit()
        dispatched += 1
    return dispatched


async def dispatch_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(dispatch_pending)
        except Exception:
            log_event("analysis_dispatcher_unavailable", level=logging.WARNING, error_code="DISPATCHER_UNAVAILABLE")
        await asyncio.sleep(settings.ai_dispatch_interval_seconds)
