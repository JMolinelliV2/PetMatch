from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import current_user, verified_user
from app.core.config import settings
from app.core.image_storage import create_download_url, delete_private_image, store_private_image
from app.analysis.service import purge_photo, schedule_photo, utcnow
from app.models import Photo, PhotoDeletion, User
from app.photo_albums import MAX_REPORT_PHOTOS, album_photos, check_capacity, lock_album, preserve_cover, set_cover
from app.species import require_supported_owner
from app.schemas import PhotoAlbumRead, PhotoCoverInput, PhotoCreate, PhotoRead, PhotoUpdate, PhotoUploadRead
from app.services.access import owner_has_access
from app.matching.linked import mark_related_pending
from app.account_management import lock_active_user

router = APIRouter(prefix="/photos", tags=["photos"])


def owned_photo(db: Session, photo_id: UUID, user: User) -> Photo:
    photo = db.get(Photo, photo_id)
    if photo is None or not owner_has_access(photo.owner_type, photo.owner_id, db, user):
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


def read_album(db, owner_type, owner_id):
    photos = album_photos(db, owner_type, owner_id)
    primary = photos[0].id if photos else None
    return PhotoAlbumRead(items=[PhotoRead.model_validate(photo).model_copy(update={"is_primary":photo.id == primary}) for photo in photos], primary_photo_id=primary)


def read_photo(db, photo):
    album = album_photos(db,photo.owner_type,photo.owner_id)
    return PhotoRead.model_validate(photo).model_copy(update={"is_primary":bool(album and album[0].id == photo.id)})


@router.get("/album", response_model=PhotoAlbumRead)
def get_album(response: Response, owner_type: str = Query(pattern="^(pet|lost_case|observation)$"), owner_id: UUID = Query(),
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not owner_has_access(owner_type, owner_id, db, user):
        raise HTTPException(404, "Aviso o reporte no encontrado.")
    response.headers["Cache-Control"] = "no-store"
    return read_album(db, owner_type, owner_id)


@router.put("/cover", response_model=PhotoAlbumRead)
def choose_cover(payload: PhotoCoverInput, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user = lock_active_user(db,user)
    if not owner_has_access(payload.owner_type, payload.owner_id, db, user):
        raise HTTPException(404, "Aviso o reporte no encontrado.")
    require_supported_owner(db,payload.owner_type,payload.owner_id)
    lock_album(db,payload.owner_type,payload.owner_id)
    set_cover(db,payload.owner_type,payload.owner_id,payload.photo_id)
    db.commit()
    return read_album(db,payload.owner_type,payload.owner_id)


@router.post("/upload-batch", response_model=PhotoAlbumRead, status_code=201)
def upload_batch(request: Request, owner_type: str = Form(pattern="^(pet|lost_case|observation)$"),
                 owner_id: UUID = Form(), files: list[UploadFile] = File(),
                 primary_index: int | None = Form(default=None,ge=0,le=4),
                 db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user = lock_active_user(db,user)
    if not owner_has_access(owner_type,owner_id,db,user):
        raise HTTPException(404,"Aviso o reporte no encontrado.")
    require_supported_owner(db,owner_type,owner_id)
    if not 1 <= len(files) <= MAX_REPORT_PHOTOS or (primary_index is not None and primary_index >= len(files)):
        raise HTTPException(422,"Elegí hasta 5 fotos y una miniatura válida.")
    lock_album(db,owner_type,owner_id)
    check_capacity(db,owner_type,owner_id,len(files))
    preserve_cover(db,owner_type,owner_id)
    stored_keys, photos = [], []
    try:
        for file in files:
            mime = file.content_type or ""
            if mime not in {"image/jpeg","image/png","image/webp"}:
                raise HTTPException(415,"Las fotos deben ser JPEG, PNG o WebP.")
            payload = file.file.read(settings.max_photo_size_bytes + 1)
            if len(payload) > settings.max_photo_size_bytes:
                raise HTTPException(413,"Cada foto debe pesar hasta 10 MB.")
            try:
                key, width, height = store_private_image(owner_type,owner_id,mime,payload)
            except ValueError as exc:
                raise HTTPException(422,"No pudimos procesar una de las fotos.") from exc
            stored_keys.append(key)
            photo = Photo(owner_type=owner_type,owner_id=owner_id,storage_key=key,mime_type=mime,width=width,height=height)
            db.add(photo); db.flush(); photos.append(photo)
            from app.product_analytics import photo_milestones
            photo_milestones(db,photo,user,request)
            schedule_photo(db,photo)
        if primary_index is not None:
            set_cover(db,owner_type,owner_id,photos[primary_index].id)
        elif len(album_photos(db,owner_type,owner_id)) == len(photos):
            set_cover(db,owner_type,owner_id,photos[0].id)
        if owner_type == "observation":
            from app.product_analytics import record
            record(db,"sighting_with_photo",owner_id,request=request,user=user)
        mark_related_pending(db,owner_type,owner_id)
        db.commit()
    except Exception:
        db.rollback()
        for key in stored_keys:
            try: delete_private_image(key)
            except Exception: pass
        raise
    return read_album(db,owner_type,owner_id)


@router.post("", response_model=PhotoRead, status_code=status.HTTP_201_CREATED)
def create_photo_metadata(payload: PhotoCreate, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    if not owner_has_access(payload.owner_type, payload.owner_id, db, user):
        raise HTTPException(status_code=404, detail="Photo owner not found")
    expected_prefix = f"{payload.owner_type}/{payload.owner_id}/"
    require_supported_owner(db, payload.owner_type, payload.owner_id)
    if not payload.storage_key.startswith(expected_prefix):
        raise HTTPException(status_code=422, detail="Storage key must be scoped to the photo owner")
    photo = Photo(**payload.model_dump())
    lock_album(db, photo.owner_type, photo.owner_id)
    check_capacity(db, photo.owner_type, photo.owner_id, 1)
    preserve_cover(db, photo.owner_type, photo.owner_id)
    db.add(photo)
    db.flush()
    if len(album_photos(db,photo.owner_type,photo.owner_id)) == 1:
        set_cover(db,photo.owner_type,photo.owner_id,photo.id)
    schedule_photo(db, photo)
    mark_related_pending(db, photo.owner_type, photo.owner_id)
    db.commit()
    db.refresh(photo)
    return read_photo(db,photo)


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
    require_supported_owner(db, owner_type, owner_id)
    lock_album(db, owner_type, owner_id)
    check_capacity(db, owner_type, owner_id, 1)
    preserve_cover(db, owner_type, owner_id)
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
        db.add(photo)
        db.flush()
        if len(album_photos(db,owner_type,owner_id)) == 1:
            set_cover(db,owner_type,owner_id,photo.id)
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
    return PhotoUploadRead(photo=read_photo(db,photo), signed_url=create_download_url(storage_key))


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
    album = album_photos(db,owner_type,owner_id)
    primary = album[0].id if album else None
    return [PhotoRead.model_validate(photo).model_copy(update={"is_primary":photo.id == primary}) for photo in db.scalars(query)]


@router.patch("/{photo_id}", response_model=PhotoRead)
def update_photo_metadata(photo_id: UUID, payload: PhotoUpdate, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    photo = owned_photo(db, photo_id, user)
    require_supported_owner(db, photo.owner_type, photo.owner_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(photo, field, value)
    db.commit()
    db.refresh(photo)
    return read_photo(db,photo)


@router.get("/{photo_id}/url")
def get_photo_url(photo_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    photo = owned_photo(db, photo_id, user)
    return {"url": create_download_url(photo.storage_key), "expires_in_seconds": 900}


@router.get("/{photo_id}/image")
def get_owned_image(photo_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    from app.routers.photo_gallery import gallery_photo_response
    return gallery_photo_response(owned_photo(db,photo_id,user))


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo_metadata(photo_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    user=lock_active_user(db,user)
    photo = owned_photo(db, photo_id, user)
    lock_album(db,photo.owner_type,photo.owner_id)
    db.add(PhotoDeletion(storage_key=photo.storage_key, available_at=utcnow()))
    purge_photo(db, photo_id)
    owner_type,owner_id = photo.owner_type,photo.owner_id
    db.delete(photo)
    db.flush()
    mark_related_pending(db, owner_type, owner_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

