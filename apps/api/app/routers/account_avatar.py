"""Own-account profile-photo management, separate from animal analysis."""
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from app.account_management import lock_account
from app.analysis.service import utcnow
from app.core.config import settings
from app.core.image_storage import delete_private_image, load_display_image, store_profile_image
from app.db.session import get_db
from app.dependencies import current_user, oauth2_scheme
from app.models import PhotoDeletion
from app.schemas import UserRead

router = APIRouter(prefix="/auth/avatar", tags=["account"])
MAX_AVATAR_BYTES = 10 * 1024 * 1024
IMAGE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Cross-Origin-Resource-Policy": "same-origin"}


@router.get("")
def get_avatar(user=Depends(current_user)):
    if not user.avatar_storage_key:
        raise HTTPException(404, "Todavía no cargaste una foto de perfil.")
    try:
        payload, mime = load_display_image(user.avatar_storage_key, "image/jpeg")
    except Exception as exc:
        logging.getLogger(__name__).warning("avatar_read_unavailable")
        raise HTTPException(503, "No pudimos cargar tu foto de perfil.") from exc
    return Response(content=payload, media_type=mime, headers=IMAGE_HEADERS)


@router.post("", response_model=UserRead)
def upload_avatar(file: UploadFile = File(), db=Depends(get_db), user=Depends(current_user), token=Depends(oauth2_scheme)):
    user = lock_account(db, user, token)
    if not user.email_verified:
        raise HTTPException(403, "Confirmá tu correo antes de subir una foto de perfil.")
    mime = file.content_type or ""
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Elegí una foto JPG, PNG o WebP.")
    limit = min(MAX_AVATAR_BYTES, settings.max_photo_size_bytes)
    payload = file.file.read(limit + 1)
    if len(payload) > limit:
        raise HTTPException(413, f"La foto supera el tamaño permitido de {max(1, limit // (1024 * 1024))} MB.")
    try:
        key = store_profile_image(user.id, mime, payload)
    except ValueError as exc:
        raise HTTPException(422, "La imagen no es válida. Elegí un JPG, PNG o WebP de hasta 24 megapíxeles.") from exc
    except Exception as exc:
        logging.getLogger(__name__).warning("avatar_upload_unavailable")
        raise HTTPException(503, "No pudimos guardar la foto. Intentá de nuevo.") from exc
    try:
        previous = user.avatar_storage_key
        user.avatar_storage_key = key
        user.avatar_version = uuid4()
        if previous:
            db.add(PhotoDeletion(storage_key=previous, available_at=utcnow()))
        db.commit()
    except Exception:
        db.rollback()
        try:
            delete_private_image(key)
        except Exception:
            logging.getLogger(__name__).warning("avatar_upload_cleanup_failed")
        raise
    db.refresh(user)
    return user


@router.delete("", response_model=UserRead)
def remove_avatar(db=Depends(get_db), user=Depends(current_user), token=Depends(oauth2_scheme)):
    user = lock_account(db, user, token)
    if user.avatar_storage_key:
        db.add(PhotoDeletion(storage_key=user.avatar_storage_key, available_at=utcnow()))
    user.avatar_storage_key = None
    user.avatar_version = None
    db.commit()
    db.refresh(user)
    return user
