"""Public report details and metadata-cleaned photos, without private contact or GPS."""
from datetime import datetime, timedelta
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.analysis.service import utcnow
from app.core.image_storage import load_analysis_image
from app.db.session import get_db
from app.models import LostCase, Observation, Photo, User
from app.photo_albums import album_order
from app.public_authors import public_publisher_name
from app.report_text import observation_description
from app.species import Species, supported_observation_scope
from app.routers.public_lost_dogs import active_dogs
from app.routers.photo_gallery import gallery_photo_response
from app.schemas import PublicPhotoList, PublicPhotoRead

router = APIRouter(prefix="/public/observations", tags=["public-observations"])


class RelatedNotice(BaseModel):
    id: UUID
    public_id: str
    name: str


class PublicObservationRead(BaseModel):
    id: UUID
    public_id: str
    species: Species
    sex: str
    primary_color: str
    size: str
    description: str
    source_type: str
    public_location: str | None
    observed_at: datetime
    photo_url: str | None
    related_notice: RelatedNotice | None
    publisher_name: str | None = None


def visible_observations():
    return select(Observation).where(
        supported_observation_scope(),
        Observation.moderation_status == "VISIBLE",
        Observation.source_type.in_(["USER_SIGHTING", "FOUND_ANIMAL"]),
        Observation.observed_at <= utcnow() + timedelta(minutes=1),
    )


def observation_photo_exists():
    return exists().where(Photo.owner_type == "observation", Photo.owner_id == Observation.id).correlate(Observation)


def public_photo_url(identity, has_photo):
    return f"/api/v1/public/observations/{identity}/photo" if has_photo else None


@router.get("/{observation_id}", response_model=PublicObservationRead)
def get_public_observation(observation_id: UUID, response: Response, db: Session = Depends(get_db)):
    row = db.execute(visible_observations().where(Observation.id == observation_id).outerjoin(User, Observation.author_id == User.id).add_columns(observation_photo_exists(), User.name)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="El reporte ya no está disponible.")
    observation, has_photo, publisher_name = row
    related_notice = None
    if observation.linked_case_id:
        related = db.execute(active_dogs().where(LostCase.id == observation.linked_case_id)).first()
        if related:
            case, pet = related
            related_notice = RelatedNotice(id=case.id, public_id=case.public_id, name=pet.name)
    response.headers["Cache-Control"] = "no-store"
    # Explicit allowlist: first name only; no author ID, contacts, storage keys or precise location.
    return PublicObservationRead(
        id=observation.id, public_id=observation.public_id, species=observation.species, sex=observation.sex,
        primary_color=observation.primary_color, size=observation.size,
        description=observation_description(observation), source_type=observation.source_type,
        public_location=observation.public_location, observed_at=observation.observed_at,
        photo_url=public_photo_url(observation.id, has_photo), related_notice=related_notice,
        publisher_name=public_publisher_name(publisher_name),
    )


@router.get("/{observation_id}/photo")
def get_public_observation_photo(observation_id: UUID, db: Session = Depends(get_db)):
    observation = db.scalar(visible_observations().where(Observation.id == observation_id))
    if observation is None:
        raise HTTPException(status_code=404, detail="El reporte ya no está disponible.")
    photo = db.scalar(select(Photo).where(Photo.owner_type == "observation", Photo.owner_id == observation.id).order_by(*album_order("observation",observation.id)).limit(1))
    if photo is None:
        raise HTTPException(status_code=404, detail="El reporte no tiene foto.")
    try:
        payload, mime_type = load_analysis_image(photo.storage_key, photo.mime_type)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            raise HTTPException(status_code=404, detail="La foto no está disponible.") from exc
        raise HTTPException(status_code=503, detail="No pudimos cargar la foto por ahora.") from exc
    except (BotoCoreError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="No pudimos cargar la foto por ahora.") from exc
    return Response(content=payload, media_type=mime_type, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{observation_id}/photos", response_model=PublicPhotoList)
def list_public_observation_photos(observation_id: UUID, response: Response, db: Session = Depends(get_db)):
    observation = db.scalar(visible_observations().where(Observation.id == observation_id))
    if observation is None:
        raise HTTPException(status_code=404, detail="El reporte ya no está disponible.")
    identities = db.scalars(select(Photo.id).where(Photo.owner_type == "observation", Photo.owner_id == observation.id).order_by(*album_order("observation",observation.id)))
    response.headers["Cache-Control"] = "no-store"
    return PublicPhotoList(items=[PublicPhotoRead(id=identity,is_primary=index == 0) for index,identity in enumerate(identities)])


@router.get("/{observation_id}/photos/{photo_id}")
def get_public_observation_gallery_photo(observation_id: UUID, photo_id: UUID, db: Session = Depends(get_db)):
    observation = db.scalar(visible_observations().where(Observation.id == observation_id))
    if observation is None:
        raise HTTPException(status_code=404, detail="El reporte ya no está disponible.")
    photo = db.scalar(select(Photo).where(Photo.id == photo_id, Photo.owner_type == "observation", Photo.owner_id == observation.id))
    if photo is None:
        raise HTTPException(status_code=404, detail="La foto no está disponible.")
    return gallery_photo_response(photo)
