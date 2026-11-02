from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.analysis.prompts import TEXT_PROMPT_VERSION, VISION_PROMPT_VERSION
from app.core.config import settings
from app.models import AnalysisJob, Embedding, FeatureSet, LostCase, Match, Notification, Observation, Pet, Photo
from app.species import owner_is_supported


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def input_hash(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def text_snapshot(db: Session, owner_type: str, owner_id: UUID) -> dict | None:
    if not owner_is_supported(db, owner_type, owner_id):
        return None
    if owner_type == "observation":
        observation = db.get(Observation, owner_id)
        if observation is None:
            return None
        return {"description": observation.description, "declared_features": {"species": observation.species, "primary_color": observation.primary_color, "size": observation.size}}
    if owner_type == "lost_case":
        case = db.get(LostCase, owner_id)
        if case is None:
            return None
        pet, description = case.pet, case.description
    elif owner_type == "pet":
        pet, description = db.get(Pet, owner_id), ""
        if pet is None:
            return None
    else:
        return None
    # Names, contact information, microchips and coordinates are not model inputs.
    return {"description": description, "declared_features": {
        name: getattr(pet, name) for name in (
            "species", "breed", "size", "primary_color", "secondary_colors",
            "coat_type", "distinctive_features", "collar_description",
        )
    }}


def photo_snapshot(photo: Photo) -> dict:
    return {"storage_key": photo.storage_key, "mime_type": photo.mime_type}


def is_current(db: Session, job: AnalysisJob) -> bool:
    if not owner_is_supported(db, job.owner_type, job.owner_id):
        return False
    if job.source_type == "embedding":
        from app.embeddings.service import is_current_embedding
        return is_current_embedding(db,job)
    expected_model=settings.ai_vision_model if job.source_type=="image" else settings.ai_text_model
    expected_prompt=VISION_PROMPT_VERSION if job.source_type=="image" else TEXT_PROMPT_VERSION
    if job.provider!=settings.ai_provider or job.model!=expected_model or job.prompt_version!=expected_prompt:
        return False
    if job.source_type in {"image", "embedding"}:
        photo = db.get(Photo, job.photo_id) if job.photo_id else None
        if photo is None or photo.owner_type != job.owner_type or photo.owner_id != job.owner_id:
            return False
        snapshot = image_snapshot(db,photo) if job.preprocessing_version != "legacy" else photo_snapshot(photo)
        # A photo must still have an existing report or pet.
        if text_snapshot(db, job.owner_type, job.owner_id) is None:
            return False
    else:
        snapshot = text_snapshot(db, job.owner_type, job.owner_id)
    return snapshot is not None and input_hash(snapshot) == job.input_hash


def owner_priority(db, owner_type, owner_id):
    if owner_type == "observation":
        return 100
    if owner_type == "lost_case":
        case = db.get(LostCase,owner_id)
        return 90 if case and case.status == "ACTIVE" else 10
    if owner_type == "pet" and db.scalar(select(LostCase.id).where(LostCase.pet_id==owner_id,LostCase.status=="ACTIVE").limit(1)):
        return 90
    return 50


def image_snapshot(db,photo):
    from app.analysis.image_preprocessing import preprocessing_id
    from app.embeddings.specs import photo_species,crop_version
    return {**photo_snapshot(photo),"species":photo_species(db,photo),
            "preprocessing":preprocessing_id(),"crop_version":crop_version()}


def _schedule(db: Session, owner_type: str, owner_id: UUID, source: str, snapshot: dict, photo_id: UUID | None = None, *, priority=None) -> AnalysisJob | None:
    if not owner_is_supported(db, owner_type, owner_id):
        return None
    model = settings.ai_vision_model if source == "image" else settings.ai_text_model
    version = VISION_PROMPT_VERSION if source == "image" else TEXT_PROMPT_VERSION
    digest = input_hash(snapshot)
    preprocessing = snapshot.get("preprocessing", "text-evidence-v2")
    key = input_hash({"owner_type": owner_type, "owner_id": str(owner_id), "photo_id": str(photo_id or ""),
                      "source": source, "input": digest, "provider": settings.ai_provider, "model": model, "version": version,"preprocessing":preprocessing})
    existing = db.scalar(select(AnalysisJob).where(AnalysisJob.deduplication_key == key))
    if existing is not None:
        return existing
    # The nested transaction handles competing requests without rolling back the report.
    from sqlalchemy.exc import IntegrityError
    try:
        with db.begin_nested():
            job = AnalysisJob(
                deduplication_key=key, owner_type=owner_type, owner_id=owner_id, photo_id=photo_id,
                source_type=source, provider=settings.ai_provider, model=model, prompt_version=version,
                input_hash=digest, input_snapshot=snapshot, max_attempts=settings.ai_max_attempts,
                available_at=utcnow(),
                preprocessing_version=preprocessing, priority=priority if priority is not None else owner_priority(db,owner_type,owner_id),
            )
            db.add(job)
            db.flush()
        return job
    except IntegrityError:
        existing = db.scalar(select(AnalysisJob).where(AnalysisJob.deduplication_key == key))
        if existing is None:
            raise
        return existing


def schedule_text(db: Session, owner_type: str, owner_id: UUID, *, priority=None) -> AnalysisJob | None:
    if not settings.ai_enabled:
        return None
    snapshot = text_snapshot(db, owner_type, owner_id)
    # Structured traits already participate directly in scoring. Only prose adds text evidence.
    return _schedule(db, owner_type, owner_id, "text", snapshot,priority=priority) if snapshot is not None and snapshot.get("description", "").strip() else None


def schedule_photo(db: Session, photo: Photo) -> AnalysisJob | None:
    if not owner_is_supported(db, photo.owner_type, photo.owner_id):
        return None
    from app.embeddings.service import schedule_embedding
    schedule_embedding(db, photo)
    if not settings.ai_enabled:
        return None
    return _schedule(db, photo.owner_type, photo.owner_id, "image", image_snapshot(db,photo), photo.id)


def schedule_owner(db: Session, owner_type: str, owner_id: UUID) -> None:
    if not owner_is_supported(db, owner_type, owner_id):
        return
    schedule_text(db, owner_type, owner_id)
    if settings.ai_enabled or settings.embeddings_enabled:
        for photo in db.scalars(select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == owner_id)):
            schedule_photo(db, photo)


def purge_owner(db: Session, owner_type: str, owner_id: UUID) -> None:
    from app.models import PhotoCover
    db.execute(delete(PhotoCover).where(PhotoCover.owner_type == owner_type, PhotoCover.owner_id == owner_id))
    if owner_type == "lost_case":
        db.execute(delete(Notification).where(Notification.lost_case_id == owner_id))
        db.execute(delete(Match).where(Match.lost_case_id == owner_id))
        db.execute(update(Observation).where(Observation.linked_case_id == owner_id).values(linked_case_id=None, matching_status="INACTIVE"))
    elif owner_type == "observation":
        db.execute(delete(Notification).where(Notification.observation_id == owner_id))
        db.execute(delete(Match).where(Match.observation_id == owner_id))
    ids = select(AnalysisJob.id).where(AnalysisJob.owner_type == owner_type, AnalysisJob.owner_id == owner_id)
    db.execute(delete(Embedding).where(Embedding.analysis_job_id.in_(ids)))
    db.execute(delete(FeatureSet).where(FeatureSet.analysis_job_id.in_(ids)))
    db.execute(delete(AnalysisJob).where(AnalysisJob.owner_type == owner_type, AnalysisJob.owner_id == owner_id))


def purge_photo(db: Session, photo_id: UUID) -> None:
    ids = select(AnalysisJob.id).where(AnalysisJob.photo_id == photo_id)
    db.execute(delete(Embedding).where(Embedding.analysis_job_id.in_(ids)))
    db.execute(delete(FeatureSet).where(FeatureSet.analysis_job_id.in_(ids)))
    db.execute(delete(AnalysisJob).where(AnalysisJob.photo_id == photo_id))
