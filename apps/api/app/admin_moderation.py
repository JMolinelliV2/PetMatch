"""Shared visibility/account controls, including session revocation and restoration guards."""
from fastapi import HTTPException
from sqlalchemy import select, update
from app.analysis.service import utcnow
from app.matching.linked import mark_related_pending
from app.models import AuthSession, LostCase, Observation, Pet, User
from app.species import require_supported_owner


def publication_author(db, target):
    return db.scalar(select(Pet.owner_id).where(Pet.id == target.pet_id)) if isinstance(target, LostCase) else target.author_id


def set_visibility(db, kind, identity, visibility):
    model = LostCase if kind == "lost_case" else Observation
    target = db.get(model, identity)
    if target is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada.")
    author_id = publication_author(db, target)
    author = db.scalar(select(User).where(User.id == author_id).with_for_update(key_share=True).execution_options(populate_existing=True)) if author_id else None
    if visibility == "VISIBLE" and author is not None and author.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Primero reactivá la cuenta del autor para restaurar esta publicación.")
    if visibility == "VISIBLE":
        require_supported_owner(db, kind, identity)
    target = db.scalar(select(model).where(model.id == identity).with_for_update(key_share=True).execution_options(populate_existing=True))
    if target is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada.")
    previous = target.moderation_status
    target.moderation_status = visibility
    db.flush()
    mark_related_pending(db, kind, identity)
    return target, previous


def set_account_status(db, identity, value, administrator_id):
    if identity == administrator_id and value == "BLOCKED":
        raise HTTPException(status_code=409, detail="No podés bloquear tu propia cuenta.")
    account = db.scalar(select(User).where(User.id == identity).with_for_update(key_share=True).execution_options(populate_existing=True))
    if account is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    previous = account.status
    account.status = value
    if value == "BLOCKED":
        db.execute(update(AuthSession).where(AuthSession.user_id == identity, AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
        cases = list(db.scalars(select(LostCase).join(Pet).where(Pet.owner_id == identity).order_by(LostCase.id).with_for_update(of=LostCase, key_share=True)))
        observations = list(db.scalars(select(Observation).where(Observation.author_id == identity).order_by(Observation.id).with_for_update(key_share=True)))
        for kind, records in (("lost_case", cases), ("observation", observations)):
            for publication in records:
                publication.moderation_status = "HIDDEN"
                db.flush()
                mark_related_pending(db, kind, publication.id)
    return account, previous
