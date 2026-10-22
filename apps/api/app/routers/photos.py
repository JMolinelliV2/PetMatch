from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import current_user, verified_user
from app.core.config import settings
from app.core.image_storage import create_download_url, delete_private_image, store_private_image
from app.analysis.service import purge_photo, schedule_photo
from app.models import Photo, User
from app.schemas import PhotoCreate, PhotoRead, PhotoUpdate, PhotoUploadRead
from app.services.access import owner_has_access
from app.matching.linked import mark_related_pending
from app.photo_reminders import lock_photo_cases
from app.account_management import lock_active_user

router = APIRouter(prefix="/photos", tags=["photos"])


def owned_photo(db: Session, photo_id: UUID, user: User) -> Photo:
    photo = db.get(Photo, photo_id)
    if photo is None or not owner_has_access(photo.owner_type, photo.owner_id, db, user):
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


@router.post("", response_model=PhotoRead, status_code=status.HTTP_201_CREATED)
def create_photo_metadata(payload: PhotoCreate, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    if not owner_has_access(payload.owner_type, payload.owner_id, db, user):
        raise HTTPException(status_code=404, detail="Photo owner not found")
    expected_prefix = f"{payload.owner_type}/{payload.owner_id}/"
    if not payload.storage_key.startswith(expected_prefix):
        raise HTTPException(status_code=422, detail="Storage key must be scoped to the photo owner")
    photo = Photo(**payload.model_dump())
    lock_photo_cases(db, photo.owner_type, photo.owner_id)
    db.add(photo)
    db.flush()
    schedule_photo(db, photo)
    mark_related_pending(db, photo.owner_type, photo.owner_id)
    db.commit()
    db.refresh(photo)
    return photo


@router.post("/upload", response_model=PhotoUploadRead, status_code=status.HTTP_201_CREATED)
def upload_photo(
    request: Request,
    owner_type: str = Form(pattern="^(pet|lost_case|observation)$"),
    owner_id: UUID = Form(),
    file: UploadFile = File(),
    db: Session = Depends(get_db),
    user: User = Depends(verified_user),
):
    user=lock_active_user(db,user)
    if not owner_has_access(owner_type, owner_id, db, user):
        raise HTTPException(status_code=404, detail="Photo owner not found")
    mime_type = file.content_type or ""
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, and WebP images are accepted")
    payload = file.file.read(settings.max_photo_size_bytes + 1)
    if len(payload) > settings.max_photo_size_bytes:
        size_mb = max(1, settings.max_photo_size_bytes // (1024 * 1024))
        raise HTTPException(status_code=413, detail=f"Image exceeds the {size_mb} MB limit")
    try:
        storage_key, width, height = store_private_image(owner_type, owner_id, mime_type, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    photo = Photo(
        owner_type=owner_type,
        owner_id=owner_id,
        storage_key=storage_key,
        mime_type=mime_type,
        width=width,
        height=height,
    )
    try:
        lock_photo_cases(db, owner_type, owner_id)
        db.add(photo)
        db.flush()
        from app.product_analytics import photo_milestones, record
        photo_milestones(db,photo,user,request)
        if owner_type=="observation":record(db,"sighting_with_photo",owner_id,request=request,user=user)
        schedule_photo(db, photo)
        mark_related_pending(db, photo.owner_type, photo.owner_id)
        db.commit()
        db.refresh(photo)
    except Exception:
        db.rollback()
        delete_private_image(storage_key)
        raise
    return PhotoUploadRead(photo=photo, signed_url=create_download_url(storage_key))


@router.get("", response_model=list[PhotoRead])
def list_photo_metadata(
    owner_type: str = Query(pattern="^(pet|lost_case|observation)$"),
    owner_id: UUID = Query(),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not owner_has_access(owner_type, owner_id, db, user):
        raise HTTPException(status_code=404, detail="Photo owner not found")
    query = select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == owner_id).order_by(Photo.created_at.desc())
    return list(db.scalars(query))


@router.patch("/{photo_id}", response_model=PhotoRead)
def update_photo_metadata(photo_id: UUID, payload: PhotoUpdate, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    photo = owned_photo(db, photo_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(photo, field, value)
    db.commit()
    db.refresh(photo)
    return photo


@router.get("/{photo_id}/url")
def get_photo_url(photo_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    photo = owned_photo(db, photo_id, user)
    return {"url": create_download_url(photo.storage_key), "expires_in_seconds": 900}


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo_metadata(photo_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    user=lock_active_user(db,user)
    photo = owned_photo(db, photo_id, user)
    delete_private_image(photo.storage_key)
    purge_photo(db, photo_id)
    mark_related_pending(db, photo.owner_type, photo.owner_id)
    db.delete(photo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

