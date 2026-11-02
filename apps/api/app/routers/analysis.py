from datetime import timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.schemas import AnalysisJobRead, FeatureSetRead, OwnerAnalysisRead
from app.analysis.service import is_current, schedule_owner, utcnow
from app.core.config import settings
from app.db.session import get_db
from app.dependencies import current_user, verified_user
from app.models import AnalysisJob, FeatureSet, User
from app.species import require_supported_owner
from app.services.access import owner_has_access

router = APIRouter(prefix="/analysis", tags=["analysis"])
OwnerType = Literal["pet", "lost_case", "observation"]


def owned_job(db: Session, job_id: UUID, user: User, lock: bool = False) -> AnalysisJob:
    query = select(AnalysisJob).where(AnalysisJob.id == job_id)
    job = db.scalar(query.with_for_update() if lock else query)
    if job is None or not owner_has_access(job.owner_type, job.owner_id, db, user):
        raise HTTPException(status_code=404, detail="Analysis not found")
    return job


def read_job(db: Session, job: AnalysisJob) -> AnalysisJobRead:
    result = AnalysisJobRead.model_validate(job)
    if job.status == "SUCCEEDED" and is_current(db, job):
        features = db.scalar(select(FeatureSet).where(FeatureSet.analysis_job_id == job.id))
        if features is not None:
            result.feature_set = FeatureSetRead.model_validate(features)
    return result


def read_owner(db: Session, owner_type: str, owner_id: UUID) -> OwnerAnalysisRead:
    jobs = db.scalars(select(AnalysisJob).where(
        AnalysisJob.owner_type == owner_type, AnalysisJob.owner_id == owner_id,
    ).order_by(AnalysisJob.created_at.desc()).limit(100))
    # Superseded descriptions never appear as the current report's characteristics.
    return OwnerAnalysisRead(enabled=settings.ai_enabled, jobs=[
        read_job(db, job) for job in jobs if is_current(db, job)
        and job.provider == settings.ai_provider
        and job.model == (settings.ai_vision_model if job.source_type == "image" else settings.ai_text_model)
    ])


@router.get("/jobs/{job_id}", response_model=AnalysisJobRead)
def get_analysis_job(job_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return read_job(db, owned_job(db, job_id, user))


@router.post("/jobs/{job_id}/retry", response_model=AnalysisJobRead, status_code=202)
def retry_analysis_job(job_id: UUID, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    job = owned_job(db, job_id, user, lock=True)
    require_supported_owner(db, job.owner_type, job.owner_id)
    if not (settings.embeddings_enabled if job.source_type == "embedding" else settings.ai_enabled):
        raise HTTPException(status_code=409, detail="Analysis is disabled")
    if not is_current(db, job):
        raise HTTPException(status_code=409, detail="Evidence has changed; request a new analysis")
    if job.status == "FAILED":
        now = utcnow()
        finished = job.finished_at.replace(tzinfo=timezone.utc) if job.finished_at and job.finished_at.tzinfo is None else job.finished_at
        if finished and now < finished + timedelta(seconds=60):
            raise HTTPException(status_code=429, detail="Wait before retrying analysis", headers={"Retry-After": "60"})
        job.status, job.attempts, job.available_at = "PENDING", 0, now
        job.error_code, job.finished_at, job.lease_expires_at, job.run_token = None, None, None, None
        db.commit()
        db.refresh(job)
    return read_job(db, job)


@router.get("/{owner_type}/{owner_id}", response_model=OwnerAnalysisRead)
def get_owner_analysis(owner_type: OwnerType, owner_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not owner_has_access(owner_type, owner_id, db, user):
        raise HTTPException(status_code=404, detail="Report not found")
    return read_owner(db, owner_type, owner_id)


@router.post("/{owner_type}/{owner_id}", response_model=OwnerAnalysisRead, status_code=202)
def start_owner_analysis(owner_type: OwnerType, owner_id: UUID, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    if not owner_has_access(owner_type, owner_id, db, user):
        raise HTTPException(status_code=404, detail="Report not found")
    if not settings.ai_enabled:
        raise HTTPException(status_code=409, detail="Analysis is disabled")
    require_supported_owner(db, owner_type, owner_id)
    schedule_owner(db, owner_type, owner_id)
    db.commit()
    return read_owner(db, owner_type, owner_id)
