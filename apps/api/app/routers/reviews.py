from typing import Literal
from uuid import UUID
import logging
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.analysis.service import utcnow
from app.db.session import get_db
from app.dependencies import current_user, verified_user
from app.models import AdminAudit, CaseReview, LostCase, Pet, User
from app.species import SUPPORTED_SPECIES, is_supported_species, require_supported_species
from app.admin_access import administrator
from app.core.image_storage import load_display_image

router = APIRouter(tags=["reviews"])
RETIRED_STATUSES = {"FOUND", "CLOSED", "CANCELLED"}


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(default="", max_length=80)
    rating: StrictInt = Field(ge=1, le=5)
    comment: str = Field(min_length=20, max_length=800)
    consent: Literal[True]

    @field_validator("display_name", "comment", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class VisibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visibility: Literal["VISIBLE", "HIDDEN"]


def owned_review_case(db, case_id, user, *, lock=False):
    query = select(LostCase).join(Pet).where(LostCase.id == case_id, Pet.owner_id == user.id)
    if lock:
        query = query.with_for_update(of=LostCase)
    case = db.scalar(query)
    if case is None:
        raise HTTPException(status_code=404, detail="Aviso no encontrado.")
    return case


def anonymous_review(item):
    name = "".join(char for char in unicodedata.normalize("NFKD", item.display_name) if not unicodedata.combining(char)).strip().casefold()
    return name in {"", "anonimo", "anonima", "anonymous"}


def review_avatar_version(item, user):
    if user and item.visibility == "VISIBLE" and not anonymous_review(item) and user.avatar_storage_key:
        return user.avatar_version
    return None


def public_review(item, user=None):
    # The review ID scopes photo access without exposing account IDs or storage keys.
    return {"id": item.id, "display_name": item.display_name, "rating": item.rating,
            "comment": item.comment, "created_at": item.created_at, "avatar_version": review_avatar_version(item, user)}


def visible_reviews():
    return select(CaseReview, User).select_from(CaseReview).join(User, CaseReview.author_id == User.id).join(LostCase, CaseReview.lost_case_id == LostCase.id).join(Pet, LostCase.pet_id == Pet.id).where(
        Pet.species.in_(SUPPORTED_SPECIES),
        CaseReview.visibility == "VISIBLE", User.status == "ACTIVE", User.email_verified_at.is_not(None),
        LostCase.status.in_(RETIRED_STATUSES), LostCase.moderation_status == "VISIBLE",
    )


@router.get("/public/reviews")
def public_reviews(response: Response, limit: int = Query(default=6, ge=1, le=12), db=Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    query = visible_reviews().order_by(CaseReview.created_at.desc(), CaseReview.id.desc()).limit(limit)
    return {"items": [public_review(item, user) for item, user in db.execute(query)]}


@router.get("/public/reviews/{review_id}/avatar")
def public_review_avatar(review_id: UUID, db=Depends(get_db)):
    row = db.execute(visible_reviews().where(CaseReview.id == review_id)).first()
    if row is None or review_avatar_version(*row) is None:
        raise HTTPException(404, "Esta reseña no tiene una foto pública disponible.")
    _, author = row
    try:
        payload, mime = load_display_image(author.avatar_storage_key, "image/jpeg")
    except Exception as exc:
        logging.getLogger(__name__).warning("review_avatar_unavailable")
        raise HTTPException(503, "No pudimos cargar la foto de esta reseña.") from exc
    return Response(content=payload, media_type=mime, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/reviews/lost-cases/{case_id}")
def review_state(case_id: UUID, response: Response, db=Depends(get_db), user=Depends(current_user)):
    case = owned_review_case(db, case_id, user)
    item = db.scalar(select(CaseReview).where(CaseReview.lost_case_id == case.id, CaseReview.author_id == user.id))
    response.headers["Cache-Control"] = "no-store"
    return {"eligible": is_supported_species(case.pet.species) and case.status in RETIRED_STATUSES and case.moderation_status == "VISIBLE",
            "email_verified": user.email_verified, "review": {**public_review(item, user), "visibility": item.visibility} if item else None}


@router.post("/reviews/lost-cases/{case_id}", status_code=201)
def create_review(case_id: UUID, payload: ReviewInput, response: Response, db=Depends(get_db), user=Depends(verified_user)):
    case = owned_review_case(db, case_id, user, lock=True)
    require_supported_species(case.pet.species)
    if case.status not in RETIRED_STATUSES or case.moderation_status != "VISIBLE":
        raise HTTPException(status_code=409, detail="Podés dejar una reseña después de cerrar el aviso o recuperar a tu mascota.")
    if db.scalar(select(CaseReview.id).where(CaseReview.lost_case_id == case.id)):
        raise HTTPException(status_code=409, detail="Ya dejaste una reseña para este aviso.")
    item = CaseReview(lost_case_id=case.id, author_id=user.id, display_name=payload.display_name or "Anónimo",
                      rating=payload.rating, comment=payload.comment, consent_at=utcnow())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya dejaste una reseña para este aviso.")
    response.headers["Cache-Control"] = "no-store"
    return {**public_review(item, user), "visibility": item.visibility}


@router.delete("/reviews/lost-cases/{case_id}", status_code=204)
def withdraw_review(case_id: UUID, db=Depends(get_db), user=Depends(current_user)):
    case = owned_review_case(db, case_id, user, lock=True)
    item = db.scalar(select(CaseReview).where(CaseReview.lost_case_id == case.id, CaseReview.author_id == user.id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Reseña no encontrada.")
    item.visibility = "WITHDRAWN"
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.patch("/admin/reviews/{review_id}")
def review_visibility(review_id: UUID, payload: VisibilityInput, response: Response, db=Depends(get_db), user=Depends(administrator)):
    item = db.scalar(select(CaseReview).where(CaseReview.id == review_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Reseña no encontrada.")
    if item.visibility == "WITHDRAWN":
        raise HTTPException(status_code=409, detail="El autor retiró esta reseña y no puede volver a publicarse.")
    item.visibility = payload.visibility
    db.add(AdminAudit(actor_id=user.id, action="RESTORE_REVIEW" if payload.visibility == "VISIBLE" else "HIDE_REVIEW",
                      target_type="case_review", target_id=item.id))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"id": item.id, "visibility": item.visibility}
