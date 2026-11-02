"""One cover per album; inherited pet photos count toward a notice's five photos."""
from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select

from app.models import LostCase, Observation, Photo, PhotoCover
from app.photo_reminders import lock_photo_cases

MAX_REPORT_PHOTOS = 5


def album_scope(db, kind, identity):
    if kind == "lost_case":
        case = db.get(LostCase, identity)
        if not case:
            raise HTTPException(404, "Aviso no encontrado.")
        return or_(and_(Photo.owner_type == kind, Photo.owner_id == identity),
                   and_(Photo.owner_type == "pet", Photo.owner_id == case.pet_id))
    return and_(Photo.owner_type == kind, Photo.owner_id == identity)


def cover_value(kind, identity):
    return select(PhotoCover.photo_id).where(PhotoCover.owner_type == kind, PhotoCover.owner_id == identity).scalar_subquery()


def album_order(kind, identity, *, pet_id=None):
    result = [(Photo.id == cover_value(kind, identity)).desc().nullslast()]
    if kind == "lost_case":
        result.append((Photo.owner_type == "lost_case").desc())
        if pet_id:
            result.append((Photo.id == cover_value("pet", pet_id)).desc().nullslast())
    return (*result, Photo.created_at.desc(), Photo.id.desc())


def album_photos(db, kind, identity):
    case = db.get(LostCase, identity) if kind == "lost_case" else None
    return list(db.scalars(select(Photo).where(album_scope(db, kind, identity)).order_by(
        *album_order(kind, identity, pet_id=case.pet_id if case else None))))


def lock_album(db, kind, identity):
    if kind in {"pet", "lost_case"}:
        lock_photo_cases(db, kind, identity)
    else:
        db.scalar(select(Observation.id).where(Observation.id == identity).with_for_update(key_share=True))


def check_capacity(db, kind, identity, incoming):
    if incoming < 1 or incoming > MAX_REPORT_PHOTOS:
        raise HTTPException(422, "Podés adjuntar entre una y cinco fotos.")
    scopes = [album_scope(db, kind, identity)]
    if kind == "pet":
        scopes += [album_scope(db, "lost_case", case_id) for case_id in
                   db.scalars(select(LostCase.id).where(LostCase.pet_id == identity))]
    if any((db.scalar(select(func.count()).select_from(Photo).where(scope)) or 0) + incoming > MAX_REPORT_PHOTOS for scope in scopes):
        raise HTTPException(409, "Cada aviso o reporte admite hasta 5 fotos. Quitá una antes de agregar otra.")


def set_cover(db, kind, identity, photo_id):
    photo = db.scalar(select(Photo).where(Photo.id == photo_id, album_scope(db, kind, identity)))
    if photo is None:
        raise HTTPException(422, "La miniatura debe ser una foto de este aviso o reporte.")
    row = db.get(PhotoCover, (kind, identity))
    if row:
        row.photo_id = photo_id
    else:
        db.add(PhotoCover(owner_type=kind, owner_id=identity, photo_id=photo_id))
    db.flush()


def preserve_cover(db, kind, identity):
    photos = album_photos(db, kind, identity)
    if photos:
        set_cover(db, kind, identity, photos[0].id)
