from datetime import datetime, timedelta
import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analysis.service import schedule_photo, utcnow
from app.core.config import settings
from app.core.image_storage import delete_private_image, store_private_image
from app.db.session import get_db
from app.dependencies import optional_user
from app.matching.linked import aware, evaluate_sighting
from app.models import LostCase, Notification, Observation, Photo, User
from app.photo_albums import MAX_REPORT_PHOTOS, set_cover
from app.species import is_supported_species, owner_is_supported
from app.schemas import CoarseGeo, LinkedSightingRead
from app.report_text import LINKED_SIGHTING_DESCRIPTION
from app.account_management import lock_active_user

router = APIRouter(prefix="/public/lost-animals", tags=["linked-sightings"])


def result(db, observation):
    notified = db.scalar(select(Notification.id).where(Notification.observation_id == observation.id, Notification.is_active.is_(True))) is not None
    return LinkedSightingRead(id=observation.id, public_id=observation.public_id, status=observation.matching_status, owner_notified=notified)


@router.post("/{case_id}/sightings", response_model=LinkedSightingRead, status_code=201)
def create_linked_sighting(
    case_id: UUID,
    request: Request,
    request_id: UUID = Form(),
    observed_at: datetime = Form(),
    latitude: float = Form(ge=-90, le=90, allow_inf_nan=False),
    longitude: float = Form(ge=-180, le=180, allow_inf_nan=False),
    location_accuracy_meters: int | None = Form(default=None, ge=0, le=100000),
    public_location: str | None = Form(default=None, max_length=350),
    analytics_geo: str | None = Form(default=None,max_length=350),
    photos: list[UploadFile] | None = File(default=None),
    primary_index: int = Form(default=0,ge=0,le=4),
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    if user:
        user=lock_active_user(db,user)
    try:geo=CoarseGeo.model_validate_json(analytics_geo).model_dump() if analytics_geo else CoarseGeo().model_dump()
    except ValueError:raise HTTPException(422,"La zona general no es válida.")
    case = db.scalar(select(LostCase).where(LostCase.id == case_id, LostCase.status == "ACTIVE").with_for_update())
    if case is None or not is_supported_species(case.pet.species) or case.moderation_status != "VISIBLE" or case.pet.owner.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="El aviso ya no está activo.")
    observed_at = aware(observed_at)
    if observed_at > utcnow() + timedelta(minutes=1):
        raise HTTPException(status_code=422, detail="La fecha del avistamiento no puede estar en el futuro.")
    uploads = photos or []
    if len(uploads) > MAX_REPORT_PHOTOS:
        raise HTTPException(status_code=422, detail="Podés adjuntar hasta 5 fotos.")
    if (uploads and primary_index >= len(uploads)) or (not uploads and primary_index != 0):
        raise HTTPException(422,"Elegí una miniatura válida.")
    images = []
    for photo in uploads:
        mime = photo.content_type or ""
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=415, detail="Las fotos deben ser JPEG, PNG o WebP.")
        payload = photo.file.read(settings.max_photo_size_bytes + 1)
        if len(payload) > settings.max_photo_size_bytes:
            raise HTTPException(status_code=413, detail="Cada foto debe pesar hasta 10 MB.")
        images.append((mime, payload))
    snapshot = {"case": str(case_id), "date": observed_at.isoformat(), "lat": latitude, "lon": longitude,
                "accuracy": location_accuracy_meters, "area": public_location,
                "photos": [hashlib.sha256(payload).hexdigest() for _, payload in images]}
    if primary_index:
        snapshot["primary_index"] = primary_index
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    previous = db.get(Observation, request_id)
    if previous:
        if previous.linked_case_id != case_id or previous.submission_hash != digest:
            raise HTTPException(status_code=409, detail="Este avistamiento ya fue enviado con otros datos.")
        return result(db, previous)
    # Species is a routing hint from the selected notice, never independent proof of identity.
    observation = Observation(
        id=request_id, author_id=user.id if user else None, linked_case_id=case_id, submission_hash=digest,
        species=case.pet.species, sex="unknown", description=LINKED_SIGHTING_DESCRIPTION, description_format="SYSTEM",
        observed_at=observed_at, latitude=latitude, longitude=longitude, location_accuracy_meters=location_accuracy_meters,
        public_location=public_location, source_type="USER_SIGHTING", matching_status="PENDING",analytics_geo=geo,
    )
    stored_keys = []
    try:
        db.add(observation)
        db.flush()
        for index,(mime, payload) in enumerate(images):
            try:
                key, width, height = store_private_image("observation", observation.id, mime, payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="No pudimos procesar una de las fotos.") from exc
            stored_keys.append(key)
            photo = Photo(owner_type="observation", owner_id=observation.id, storage_key=key, mime_type=mime, width=width, height=height)
            db.add(photo)
            db.flush()
            if index == primary_index:
                set_cover(db,"observation",observation.id,photo.id)
            schedule_photo(db, photo)
        evaluate_sighting(db, observation.id)
        from app.product_analytics import record
        for name in ("sighting_created","sighting_authenticated" if user else "sighting_anonymous","sighting_linked"):
            record(db,name,observation.id,request=request,user=user,entity=observation)
        if images:record(db,"sighting_with_photo",observation.id,request=request,user=user,entity=observation)
        db.commit()
        db.refresh(observation)
    except Exception as exc:
        db.rollback()
        for key in stored_keys:
            try:
                delete_private_image(key)
            except Exception:
                pass
        if isinstance(exc, IntegrityError):
            previous = db.get(Observation, request_id)
            if previous and previous.linked_case_id == case_id and previous.submission_hash == digest:
                return result(db, previous)
        raise
    return result(db, observation)


@router.get("/{case_id}/sightings/{sighting_id}/status", response_model=LinkedSightingRead)
def linked_sighting_status(case_id: UUID, sighting_id: UUID, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    observation = db.scalar(select(Observation).where(Observation.id == sighting_id, Observation.linked_case_id == case_id))
    if observation is None or not owner_is_supported(db,"observation",observation.id):
        raise HTTPException(status_code=404, detail="Avistamiento no encontrado.")
    return result(db, observation)
