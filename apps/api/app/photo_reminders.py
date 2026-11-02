"""One delayed reminder per notice, checked against its current photo state."""
import asyncio
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime
import logging

from sqlalchemy import and_, or_, select

from app.analysis.service import utcnow
from app.core.config import settings
from app.db.session import SessionLocal
from app.mail_templates import add_photo_reminder_content
from app.models import LostCase, Pet, Photo, PhotoReminder, User
from app.notifications.email import send_message
from app.operational_tracking import record_mail


def has_photo(db, case):
    return db.scalar(select(Photo.id).where(or_(
        and_(Photo.owner_type == "lost_case", Photo.owner_id == case.id),
        and_(Photo.owner_type == "pet", Photo.owner_id == case.pet_id),
    )).limit(1)) is not None


def schedule_reminder(db, case):
    from app.species import is_supported_species
    if not is_supported_species(case.pet.species):
        return
    if case.status != "ACTIVE" or case.moderation_status != "VISIBLE" or has_photo(db, case):
        return
    if db.get(PhotoReminder, case.id) is None:
        db.add(PhotoReminder(lost_case_id=case.id, available_at=utcnow() + timedelta(minutes=settings.photo_reminder_delay_minutes)))


def lock_photo_cases(db, owner_type, owner_id):
    # NO KEY UPDATE serializes photos/reminders without blocking matching's foreign-key inserts.
    if owner_type not in {"pet", "lost_case"}:
        return
    pet_id=owner_id if owner_type=="pet" else db.scalar(select(LostCase.pet_id).where(LostCase.id==owner_id))
    # Pet -> cases matches account deletion; also serializes photo threshold crossings across uploads.
    db.scalar(select(Pet.id).where(Pet.id==pet_id).with_for_update(of=Pet,key_share=True))
    scope = LostCase.pet_id == owner_id if owner_type == "pet" else LostCase.id == owner_id
    list(db.scalars(select(LostCase.id).where(scope).order_by(LostCase.id).with_for_update(of=LostCase, key_share=True)))


def build_message(case, pet, owner):
    message = EmailMessage()
    message["From"], message["To"] = settings.smtp_from, owner.email
    message["Subject"] = "Una foto puede ayudar a encontrar a tu mascota"
    message["Date"] = format_datetime(utcnow())
    message["Message-ID"] = f"<mascomatch-photo-{case.id}@mascomatch.com>"
    url = f"{settings.public_site_url.rstrip('/')}/mis-avisos?foto={case.id}#fotos-{case.id}"
    add_photo_reminder_content(message, pet.name, url, f"{settings.public_site_url.rstrip('/')}/mi-cuenta#notificaciones")
    return message


def deliver_pending(session_factory=None):
    from app.species import is_supported_species
    if settings.mail_delivery_mode == "disabled":
        return 0
    factory = session_factory or SessionLocal
    with factory() as db:
        identities = list(db.scalars(select(PhotoReminder.lost_case_id).where(
            PhotoReminder.status == "PENDING", PhotoReminder.available_at <= utcnow(),
        ).order_by(PhotoReminder.available_at, PhotoReminder.lost_case_id).limit(10)))
    sent = 0
    for identity in identities:
        with factory() as db:
            owner_id = db.scalar(select(Pet.owner_id).join(LostCase, LostCase.pet_id == Pet.id).where(LostCase.id == identity))
            owner = db.scalar(select(User).where(User.id == owner_id)
                .with_for_update(skip_locked=True, key_share=True).execution_options(populate_existing=True)) if owner_id else None
            if owner is None:
                continue
            case = db.scalar(select(LostCase).where(LostCase.id == identity).with_for_update(skip_locked=True, key_share=True))
            if case is None:
                continue
            reminder = db.scalar(select(PhotoReminder).where(
                PhotoReminder.lost_case_id == identity, PhotoReminder.status == "PENDING", PhotoReminder.available_at <= utcnow(),
            ).with_for_update())
            if reminder is None:
                continue
            pet = db.get(Pet, case.pet_id)
            if not is_supported_species(pet.species) or case.status != "ACTIVE" or case.moderation_status != "VISIBLE" or not owner or owner.status != "ACTIVE" or has_photo(db, case):
                reminder.status = "CANCELLED"
            elif owner.notification_preferences.get("email", True) is False:
                reminder.status = "SKIPPED"
            elif not owner.email_verified:
                reminder.available_at = utcnow() + timedelta(minutes=5)
            else:
                reminder.attempts += 1
                try:
                    send_message(build_message(case, pet, owner))
                    reminder.status = "PREVIEWED" if settings.mail_delivery_mode == "preview" else "SENT"
                    reminder.sent_at = utcnow()
                    record_mail(db, "PHOTO_REMINDER", "photo_reminder", [case.id], owner.id, reminder.status)
                    sent += 1
                except Exception:
                    record_mail(db, "PHOTO_REMINDER", "photo_reminder", [case.id], owner.id, "FAILED")
                    reminder.status = "FAILED" if reminder.attempts >= 5 else "PENDING"
                    reminder.available_at = utcnow() + timedelta(seconds=min(3600, 30 * 2 ** reminder.attempts))
                    logging.getLogger("mascomatch.photos").warning("photo_reminder_delivery_failed")
            db.commit()
    return sent


async def delivery_loop():
    while True:
        try:
            await asyncio.to_thread(deliver_pending)
        except Exception:
            logging.getLogger("mascomatch.photos").warning("photo_reminder_delivery_unavailable")
        await asyncio.sleep(10)
