import re
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.image_storage import load_analysis_image
from app.db.session import get_db
from app.models import LostCase, Pet, Photo, User
from app.photo_albums import album_order
from app.public_authors import public_publisher_name
from app.species import SUPPORTED_SPECIES
from app.schemas import PublicLostDogList, PublicLostDogRead, PublicPhotoList, PublicPhotoRead
from app.routers.photo_gallery import gallery_photo_response

router = APIRouter(prefix="/public/lost-animals", tags=["public-lost-animals"])
legacy_router = APIRouter(prefix="/public/lost-dogs", include_in_schema=False)


def active_dogs():
    return select(LostCase, Pet).select_from(LostCase).join(Pet, LostCase.pet_id == Pet.id).join(User,Pet.owner_id==User.id).where(Pet.species.in_(SUPPORTED_SPECIES),LostCase.status == "ACTIVE",LostCase.moderation_status=="VISIBLE",User.status=="ACTIVE")


def photo_scope(case: LostCase):
    return or_(
        and_(Photo.owner_type == "lost_case", Photo.owner_id == case.id),
        and_(Photo.owner_type == "pet", Photo.owner_id == case.pet_id),
    )


def public_area(case: LostCase) -> str | None:
    if case.public_location:
        return case.public_location
    # Older web reports stored only the locality as a separate 'Zona:' line.
    for line in case.description.splitlines():
        if line.startswith("Zona: "):
            return line[6:].strip()[:350] or None
    return None


def notice(case: LostCase, pet: Pet, has_photo: bool, publisher_name: str | None = None) -> PublicLostDogRead:
    # Explicit allowlist: only the publisher's first name, without account/contact data.
    return PublicLostDogRead(
        id=case.id, public_id=case.public_id, name=pet.name, species=pet.species, sex=pet.sex, breed=pet.breed, size=pet.size,
        primary_color=pet.primary_color, description=case.description,
        public_location=public_area(case), lost_at=case.lost_at,
        photo_url=f"/api/v1/public/lost-animals/{case.id}/photo" if has_photo else None,
        publisher_name=public_publisher_name(publisher_name),
    )


@router.get("", response_model=PublicLostDogList)
@legacy_router.get("", response_model=PublicLostDogList)
def list_public_lost_dogs(
    response: Response,
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=24, ge=1, le=48),
    offset: int = Query(default=0, ge=0, le=10000),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    query = active_dogs()
    term = q.strip().lower()
    if term:
        code_match = re.fullmatch(r"mm-([0-9]{1,19})", term)
        number = int(code_match.group(1)) if code_match else 0
        code_filter = LostCase.public_number == number if 0 < number <= 9223372036854775807 else False
        query = query.where(or_(
            code_filter,
            func.lower(Pet.name).contains(term, autoescape=True),
            func.lower(LostCase.description).contains(term, autoescape=True),
            func.lower(LostCase.public_location).contains(term, autoescape=True),
        ))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    photo_exists = exists().where(or_(
        and_(Photo.owner_type == "lost_case", Photo.owner_id == LostCase.id),
        and_(Photo.owner_type == "pet", Photo.owner_id == Pet.id),
    )).correlate(LostCase, Pet)
    rows = db.execute(query.add_columns(photo_exists, User.name).order_by(LostCase.created_at.desc(), LostCase.id.desc()).offset(offset).limit(limit))
    return PublicLostDogList(items=[notice(case, pet, has_photo, publisher_name) for case, pet, has_photo, publisher_name in rows], total=total, limit=limit, offset=offset)


@router.get("/{case_id}", response_model=PublicLostDogRead)
@legacy_router.get("/{case_id}", response_model=PublicLostDogRead)
def get_public_lost_dog(case_id: UUID, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    row = db.execute(active_dogs().where(LostCase.id == case_id).add_columns(User.name)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Public notice not found")
    case, pet, publisher_name = row
    has_photo = db.scalar(select(Photo.id).where(photo_scope(case)).limit(1)) is not None
    return notice(case, pet, has_photo, publisher_name)


@router.get("/{case_id}/photo")
@legacy_router.get("/{case_id}/photo")
def get_public_lost_dog_photo(case_id: UUID, db: Session = Depends(get_db)):
    row = db.execute(active_dogs().where(LostCase.id == case_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Public notice not found")
    case, _ = row
    photo = db.scalar(select(Photo).where(photo_scope(case)).order_by(*album_order("lost_case",case.id,pet_id=case.pet_id)).limit(1))
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    try:
        payload, mime_type = load_analysis_image(photo.storage_key, photo.mime_type)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            raise HTTPException(status_code=404, detail="Photo not found") from exc
        raise HTTPException(status_code=503, detail="Photo temporarily unavailable") from exc
    except (BotoCoreError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Photo temporarily unavailable") from exc
    return Response(content=payload, media_type=mime_type, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{case_id}/photos", response_model=PublicPhotoList)
@legacy_router.get("/{case_id}/photos", response_model=PublicPhotoList)
def list_public_lost_dog_photos(case_id: UUID, response: Response, db: Session = Depends(get_db)):
    row = db.execute(active_dogs().where(LostCase.id == case_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Public notice not found")
    case, _ = row
    identities = db.scalars(select(Photo.id).where(photo_scope(case)).order_by(*album_order("lost_case",case.id,pet_id=case.pet_id)))
    response.headers["Cache-Control"] = "no-store"
    return PublicPhotoList(items=[PublicPhotoRead(id=identity,is_primary=index == 0) for index,identity in enumerate(identities)])


@router.get("/{case_id}/photos/{photo_id}")
@legacy_router.get("/{case_id}/photos/{photo_id}")
def get_public_lost_dog_gallery_photo(case_id: UUID, photo_id: UUID, db: Session = Depends(get_db)):
    row = db.execute(active_dogs().where(LostCase.id == case_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Public notice not found")
    case, _ = row
    photo = db.scalar(select(Photo).where(Photo.id == photo_id, photo_scope(case)))
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return gallery_photo_response(photo)
