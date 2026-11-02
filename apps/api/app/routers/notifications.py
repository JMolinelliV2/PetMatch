from typing import Literal
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case as sql_case, func, select, update
from sqlalchemy.orm import Session

from app.analysis.service import utcnow
from app.matching.linked import aware
from app.core.image_storage import load_analysis_image
from app.db.session import get_db
from app.dependencies import current_user
from app.models import LostCase, Match, Notification, Observation, Pet, Photo, User
from app.photo_albums import album_order
from app.species import SUPPORTED_SPECIES
from app.schemas import NotificationList, NotificationRead
from app.report_text import notification_body
from app.routers.photo_gallery import gallery_photo_response
from app.matching.visibility import presentation

router = APIRouter(prefix="/notifications", tags=["notifications"])


def private_notifications(user):
    return select(Notification, LostCase, Pet, Observation).join(LostCase, Notification.lost_case_id == LostCase.id).join(Pet, LostCase.pet_id == Pet.id).join(Observation, Notification.observation_id == Observation.id).where(
        Pet.species.in_(SUPPORTED_SPECIES), Observation.species.in_(SUPPORTED_SPECIES),
        Notification.owner_id == user.id, Pet.owner_id == user.id, Notification.is_active.is_(True), LostCase.status == "ACTIVE",
        LostCase.moderation_status=="VISIBLE",Observation.moderation_status=="VISIBLE",
    )


def owned_row(db, identity, user):
    row = db.execute(private_notifications(user).where(Notification.id == identity)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Notificación no encontrada.")
    return row


def serialize(db, row):
    notification, case, pet, observation = row
    match = db.get(Match, notification.match_id) if notification.match_id else None
    author=db.get(User,observation.author_id) if observation.share_contact and observation.author_id else None
    photos = list(db.scalars(select(Photo.id).where(Photo.owner_type == "observation", Photo.owner_id == observation.id).order_by(*album_order("observation",observation.id))))
    return NotificationRead(
        presentation=presentation(match,pet.owner,1,"NOTIFICATION") if match and match.recommended_at else None,
        id=notification.id, kind=notification.kind, title=notification.title, body=notification_body(notification.body),
        read_at=notification.read_at, created_at=aware(notification.created_at), lost_case_id=case.id,
        lost_case_public_id=case.public_id, observation_public_id=observation.public_id,
        archived_at=notification.archived_at,
        pet_name=pet.name, observed_at=aware(observation.observed_at), public_location=observation.public_location,
        latitude=observation.latitude, longitude=observation.longitude,
        reasons=match.explanation if match else observation.matching_reasons, photo_ids=photos,
        email_status=notification.email_status,
        match_id=notification.match_id, match_status=match.status if match else None,
        reporter_contact=author.email if author and author.status=="ACTIVE" and author.email_verified else None,
        matching_status=observation.matching_status,linked_to_notice=observation.linked_case_id==case.id,
    )


@router.get("", response_model=NotificationList)
def list_notifications(response: Response, limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0, le=10000), view: Literal["all", "unread", "archived"] = "all", db: Session = Depends(get_db), user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    available = private_notifications(user)
    query = available.where(Notification.archived_at.is_not(None) if view == "archived" else Notification.archived_at.is_(None))
    if view == "unread":
        query = query.where(Notification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    unread = db.scalar(select(func.count()).select_from(available.where(Notification.archived_at.is_(None), Notification.read_at.is_(None)).subquery())) or 0
    rows = list(db.execute(query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(offset).limit(limit)))
    return NotificationList(items=[serialize(db, row) for row in rows], unread_count=unread, total=total)


def cancel_pending_email():
    return sql_case((Notification.email_status == "PENDING", "CANCELLED"), else_=Notification.email_status)


@router.patch("/read-all")
def mark_all_read(response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    now = utcnow()
    identities = private_notifications(user).with_only_columns(Notification.id).where(Notification.archived_at.is_(None), Notification.created_at <= now)
    result = db.execute(update(Notification).where(Notification.id.in_(identities), Notification.read_at.is_(None)).values(read_at=now, email_status=cancel_pending_email()).execution_options(synchronize_session=False))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"updated": result.rowcount, "read_at": now}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_read(notification_id: UUID, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    row = owned_row(db, notification_id, user)
    db.execute(update(Notification).where(Notification.id == row[0].id, Notification.owner_id == user.id).values(read_at=func.coalesce(Notification.read_at, utcnow()), email_status=cancel_pending_email()).execution_options(synchronize_session=False))
    db.commit()
    return serialize(db, row)


@router.patch("/{notification_id}/archive", response_model=NotificationRead)
def archive_notification(notification_id: UUID, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = owned_row(db, notification_id, user)
    now = utcnow()
    db.execute(update(Notification).where(Notification.id == row[0].id, Notification.owner_id == user.id).values(archived_at=func.coalesce(Notification.archived_at, now), read_at=func.coalesce(Notification.read_at, now), email_status=cancel_pending_email()).execution_options(synchronize_session=False))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return serialize(db, row)


@router.patch("/{notification_id}/restore", response_model=NotificationRead)
def restore_notification(notification_id: UUID, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = owned_row(db, notification_id, user)
    db.execute(update(Notification).where(Notification.id == row[0].id, Notification.owner_id == user.id).values(archived_at=None).execution_options(synchronize_session=False))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return serialize(db, row)


@router.get("/{notification_id}", response_model=NotificationRead)
def get_notification(notification_id: UUID, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    result=serialize(db, owned_row(db, notification_id, user))
    match=db.get(Match,result.match_id) if result.match_id else None
    if match and match.recommended_at:
        from app.matching.visibility import presentation
        result.presentation=presentation(match,user,1,"NOTIFICATION")
    return result


@router.get("/{notification_id}/photos/{photo_id}")
def notification_photo(notification_id: UUID, photo_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    observation = owned_row(db, notification_id, user)[3]
    photo = db.scalar(select(Photo).where(Photo.id == photo_id, Photo.owner_type == "observation", Photo.owner_id == observation.id))
    if photo is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada.")
    try:
        payload, mime_type = load_analysis_image(photo.storage_key, photo.mime_type)
    except (BotoCoreError, ClientError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Foto no disponible en este momento.") from exc
    return Response(payload, media_type=mime_type, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{notification_id}/photos/{photo_id}/large")
def notification_gallery_photo(notification_id: UUID, photo_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    observation = owned_row(db, notification_id, user)[3]
    photo = db.scalar(select(Photo).where(Photo.id == photo_id, Photo.owner_type == "observation", Photo.owner_id == observation.id))
    if photo is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada.")
    return gallery_photo_response(photo)
