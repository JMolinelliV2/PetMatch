"""Minimal public health and token-protected operational metrics."""
from datetime import datetime, timezone
import hmac
import urllib.request
import json
import math
from app.core.image_storage import _client
from fastapi import APIRouter, Header, HTTPException, Response
from redis import Redis
from sqlalchemy import select, func, text
from app.analysis.service import utcnow
from app.core.config import settings
from app.db.session import SessionLocal
from app.matching.linked import aware
from app.models import AccountToken, AnalysisJob, ContactMessage, Notification

router = APIRouter(tags=["operations"])


def require_metrics(authorization):
    secret=settings.metrics_token.get_secret_value()
    if not secret or not authorization or not hmac.compare_digest(authorization.encode(),("Bearer "+secret).encode()):
        raise HTTPException(status_code=404,detail="Not found")


@router.get("/internal/ready/ai",include_in_schema=False)
def ai_ready(authorization: str|None=Header(default=None)):
    require_metrics(authorization)
    from app.ops.ai_health import ai_readiness
    checks={**readiness(),**ai_readiness()}
    return Response(json.dumps({"ready":all(checks.values()),"checks":checks}),status_code=200 if all(checks.values()) else 503,
                    media_type="application/json",headers={"Cache-Control":"no-store"})


def readiness():
    checks = {"database":False, "queue":False, "photos":False}
    try:
        with SessionLocal() as db:
            checks["database"] = db.scalar(text("SELECT 1")) == 1
    except Exception:
        pass
    try:
        with Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2) as redis:
            checks["queue"] = bool(redis.ping())
    except Exception:
        pass
    try:
        _client(settings.s3_endpoint).head_bucket(Bucket=settings.s3_bucket)
        checks["photos"] = True
    except Exception:
        pass
    return checks


@router.get("/health/ready")
def ready():
    checks = readiness()
    ok = all(checks.values())
    return Response('{"status":"' + ("ok" if ok else "unavailable") + '"}',
                    status_code=200 if ok else 503, media_type="application/json", headers={"Cache-Control":"no-store"})


@router.get("/internal/metrics", include_in_schema=False)
def metrics(authorization: str | None = Header(default=None)):
    secret = settings.metrics_token.get_secret_value()
    if not secret or not authorization or not hmac.compare_digest(authorization.encode(), ("Bearer " + secret).encode()):
        raise HTTPException(status_code=404, detail="Not found")
    values = {"mascomatch_ready":float(all(readiness().values())),
              "mascomatch_email_enabled":float(settings.mail_delivery_mode == "smtp")}
    from app.ops.resources import container_resources
    for name,value in container_resources().items():values[f'mascomatch_container_{name}{{service="api"}}']=value
    try:
        with SessionLocal() as db:
            from app.models import ProductEvent
            values["mascomatch_analytics_rollup_pending"]=db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.aggregated.is_(False))) or 0
            from datetime import timedelta
            from app.ops.ai_health import ai_readiness
            for name,ok in ai_readiness().items():
                values["mascomatch_ai_ready{component=\""+name+"\"}"]=int(ok)
            cutoff=utcnow()-timedelta(hours=24)
            jobs=list(db.scalars(select(AnalysisJob).where(AnalysisJob.started_at>=cutoff).order_by(AnalysisJob.started_at.desc()).limit(10000)))
            for source in ("text","image","embedding"):
                subset=[job for job in jobs if job.source_type==source]
                for metric in ("total_ms","model_load_ms","load_image_ms","preprocess_image_ms","ollama_request_ms","parse_validate_ms","persist_result_ms","trigger_matching_ms","cpu_ms"):
                    samples=sorted(float(job.metrics[metric]) for job in subset if metric in (job.metrics or {}) and math.isfinite(float(job.metrics[metric])))
                    for quantile in (.5,.95):
                        value=samples[min(len(samples)-1,math.ceil(len(samples)*quantile)-1)] if samples else 0
                        values[f'mascomatch_analysis_{metric}{{source="{source}",quantile="{quantile}"}}']=value
                for metric in ("retries","timeouts","invalid_responses","incomplete_responses","cold_start"):
                    values[f'mascomatch_analysis_{metric}_24h{{source="{source}"}}']=sum((job.metrics or {}).get(metric,0) for job in subset)
                values[f'mascomatch_analysis_jobs_last_minute{{source="{source}"}}']=sum(1 for job in subset if job.finished_at and aware(job.finished_at)>=utcnow()-timedelta(minutes=1))
                values[f'mascomatch_analysis_queue{{source="{source}"}}']=db.scalar(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.source_type==source,AnalysisJob.status.in_(["PENDING","QUEUED","DISPATCHING","RUNNING"])))
                source_oldest=db.scalar(select(func.min(AnalysisJob.created_at)).where(AnalysisJob.source_type==source,AnalysisJob.status.in_(["PENDING","QUEUED","DISPATCHING","RUNNING"])))
                values[f'mascomatch_analysis_oldest_seconds_by_source{{source="{source}"}}']=max(0,(utcnow()-aware(source_oldest)).total_seconds()) if source_oldest else 0
            urgent_oldest=db.scalar(select(func.min(AnalysisJob.created_at)).where(AnalysisJob.priority>=90,AnalysisJob.status.in_(["PENDING","QUEUED","DISPATCHING","RUNNING"])))
            values["mascomatch_analysis_urgent_oldest_seconds"]=max(0,(utcnow()-aware(urgent_oldest)).total_seconds()) if urgent_oldest else 0
            visual=[job for job in jobs if job.source_type=="embedding"]
            values["mascomatch_crop_detection_ratio_24h"]=sum(bool((job.metrics or {}).get("detected")) for job in visual)/len(visual) if visual else 0
            values["mascomatch_analysis_failed"] = db.scalar(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.status == "FAILED"))
            values["mascomatch_analysis_pending"] = db.scalar(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.status.in_(["PENDING","DISPATCHING","QUEUED","RUNNING"])))
            oldest = db.scalar(select(func.min(AnalysisJob.created_at)).where(AnalysisJob.status.in_(["PENDING","DISPATCHING","QUEUED","RUNNING"])))
            values["mascomatch_analysis_oldest_seconds"] = max(0, (utcnow()-aware(oldest)).total_seconds()) if oldest else 0
            values["mascomatch_email_failed"] = db.scalar(select(func.count()).select_from(Notification).where(Notification.email_status == "FAILED", Notification.is_active.is_(True), Notification.read_at.is_(None), Notification.archived_at.is_(None)))
            values["mascomatch_email_pending"] = db.scalar(select(func.count()).select_from(Notification).where(Notification.email_status == "PENDING", Notification.is_active.is_(True), Notification.read_at.is_(None), Notification.archived_at.is_(None)))
            values["mascomatch_account_email_failed"] = db.scalar(select(func.count()).select_from(AccountToken).where(AccountToken.email_status == "FAILED"))
            values["mascomatch_contact_email_failed"] = db.scalar(select(func.count()).select_from(ContactMessage).where(ContactMessage.email_status == "FAILED"))
            values["mascomatch_contact_email_pending"] = db.scalar(select(func.count()).select_from(ContactMessage).where(ContactMessage.email_status == "PENDING"))
    except Exception:
        values["mascomatch_ready"] = 0
    try:
        with Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2) as redis:
            for status, count in redis.hgetall("mascomatch:metrics:http").items():
                if status in {b"1xx",b"2xx",b"3xx",b"4xx",b"5xx"}:
                    values[f'mascomatch_http_requests_total{{status_class="{status.decode()}"}}'] = int(count)
            values["mascomatch_backup_last_success_unixtime"] = float(redis.get("mascomatch:backup:last_success") or 0)
            prewarm=json.loads(redis.get("mascomatch:prewarm:last") or "{}")
            values["mascomatch_gemma_prewarm_ms"]=float(prewarm.get("duration_ms",0))
            values["mascomatch_gemma_prewarm_ready"]=int(prewarm.get("status")=="ready")
            for kind in ("visual","semantic"):
                heartbeat=json.loads(redis.get("mascomatch:worker:"+kind) or "{}")
                if heartbeat:
                    values[f'mascomatch_worker_busy{{kind="{kind}"}}']=int(bool(heartbeat.get("busy")))
                    for name,value in heartbeat.get("resources",{}).items():
                        if name in {"memory_bytes","memory_limit_bytes","cpu_seconds_total","cpu_limit_cores"}:
                            values[f'mascomatch_container_{name}{{service="worker-{kind}"}}']=float(value)
    except Exception:
        values["mascomatch_ready"] = 0
    return Response("\n".join(f"{name} {value}" for name,value in sorted(values.items()))+"\n",
                    media_type="text/plain; version=0.0.4", headers={"Cache-Control":"no-store"})
