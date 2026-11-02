"""Account changes are serialized with deletion and token consumption."""
import asyncio
from datetime import timedelta
import logging
from uuid import UUID
import jwt
from fastapi import HTTPException
from sqlalchemy import delete, or_, and_, select, update
from app.analysis.service import purge_owner, purge_photo, utcnow
from app.core.image_storage import delete_private_image
from app.core.security import decode_token_claims
from app.db.session import SessionLocal
from app.models import AuthSession, CaseReview, LostCase, Observation, Pet, Photo, PhotoDeletion, User


def lock_active_user(db, user):
    fresh = db.scalar(select(User).where(User.id == user.id).with_for_update(key_share=True).execution_options(populate_existing=True))
    if not fresh or fresh.status != "ACTIVE":
        raise HTTPException(401, "La sesión ya no está disponible. Ingresá de nuevo.")
    return fresh


def lock_account(db, user, token):
    try:
        session_id = UUID(decode_token_claims(token)["jti"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, "La sesión ya no está disponible. Ingresá de nuevo.")
    fresh = lock_active_user(db, user)
    if not db.scalar(select(AuthSession.id).where(AuthSession.id == session_id, AuthSession.user_id == fresh.id,
                                                AuthSession.revoked_at.is_(None), AuthSession.expires_at > utcnow())):
        raise HTTPException(401, "La sesión ya no está disponible. Ingresá de nuevo.")
    return fresh


def delete_account(db, user):
    # User -> pet -> case locks prevent concurrent account uploads or new owned records.
    if user.avatar_storage_key:
        db.add(PhotoDeletion(storage_key=user.avatar_storage_key, available_at=utcnow()))
    pets = list(db.scalars(select(Pet).where(Pet.owner_id == user.id).order_by(Pet.id).with_for_update()))
    pet_ids = [pet.id for pet in pets]
    cases = list(db.scalars(select(LostCase).where(LostCase.pet_id.in_(pet_ids)).order_by(LostCase.id).with_for_update(key_share=True)))
    case_ids = [case.id for case in cases]
    linked_ids = list(db.scalars(select(Observation.id).where(Observation.linked_case_id.in_(case_ids))))
    for case in cases:
        purge_owner(db, "lost_case", case.id)
    for pet in pets:
        purge_owner(db, "pet", pet.id)
    photos = list(db.scalars(select(Photo).where(or_(
        and_(Photo.owner_type == "lost_case", Photo.owner_id.in_(case_ids)),
        and_(Photo.owner_type == "pet", Photo.owner_id.in_(pet_ids))))))
    for photo in photos:
        purge_photo(db, photo.id)
        db.add(PhotoDeletion(storage_key=photo.storage_key, available_at=utcnow()))
        db.delete(photo)
    db.execute(update(Observation).where(Observation.author_id == user.id).values(author_id=None, share_contact=False))
    db.execute(update(Observation).where(Observation.id.in_(linked_ids)).values(
        matching_status="PENDING", matching_score=None, matching_reasons=[], matching_checked_at=None))
    db.execute(delete(CaseReview).where(CaseReview.author_id == user.id))
    db.flush()
    # Bulk deletes avoid ORM attempts to null the required owner/pet foreign keys.
    db.execute(delete(LostCase).where(LostCase.id.in_(case_ids)))
    db.execute(delete(Pet).where(Pet.id.in_(pet_ids)))
    from app.models import ProductEvent, AnalyticsSession, ProductDaily
    from app.product_analytics import digest
    db.execute(delete(ProductEvent).where(ProductEvent.user_id==user.id))
    db.execute(update(AnalyticsSession).where(AnalyticsSession.user_id==user.id).values(user_id=None))
    # Remove the linkable daily user key; aggregate counts for other visitors remain intact.
    db.execute(delete(ProductDaily).where(ProductDaily.actor_key==digest("user:"+str(user.id))))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()


def cleanup_photos():
    with SessionLocal() as db:
        ids = list(db.scalars(select(PhotoDeletion.id).where(PhotoDeletion.available_at <= utcnow()).limit(10)))
    for identity in ids:
        with SessionLocal() as db:
            job = db.scalar(select(PhotoDeletion).where(PhotoDeletion.id == identity).with_for_update(skip_locked=True))
            if not job or job.available_at > utcnow():
                continue
            try:
                delete_private_image(job.storage_key)
                db.delete(job)
            except Exception:
                job.attempts += 1
                job.available_at = utcnow() + timedelta(seconds=min(3600, 30 * 2 ** min(job.attempts, 7)))
                logging.getLogger(__name__).warning("account_photo_cleanup_retry")
            db.commit()


async def cleanup_loop():
    while True:
        try:
            await asyncio.to_thread(cleanup_photos)
        except Exception:
            logging.getLogger(__name__).warning("account_photo_cleanup_failed")
        await asyncio.sleep(10)
