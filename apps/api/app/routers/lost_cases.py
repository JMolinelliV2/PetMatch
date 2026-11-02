from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.analysis.service import purge_owner, schedule_text
from app.dependencies import current_user, verified_user
from app.models import LostCase, Pet, User
from app.species import require_supported_species
from app.schemas import LostCaseCreate, LostCaseRead, LostCaseUpdate
from app.matching.linked import mark_related_pending
from app.photo_reminders import schedule_reminder
from app.account_management import lock_active_user

router = APIRouter(prefix="/lost-cases", tags=["lost-cases"])


def owned_case(db: Session, case_id: UUID, user: User) -> LostCase:
    case = db.scalar(select(LostCase).join(Pet).where(LostCase.id == case_id, Pet.owner_id == user.id).with_for_update(of=LostCase))
    if case is None:
        raise HTTPException(status_code=404, detail="Lost case not found")
    return case


@router.post("", response_model=LostCaseRead, status_code=status.HTTP_201_CREATED)
def create_lost_case(payload: LostCaseCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    pet = db.scalar(select(Pet).where(Pet.id == payload.pet_id, Pet.owner_id == user.id))
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found")
    require_supported_species(pet.species)
    case = LostCase(**payload.model_dump())
    db.add(case)
    db.flush()
    schedule_text(db, "lost_case", case.id)
    mark_related_pending(db, "lost_case", case.id)
    schedule_reminder(db, case)
    from app.product_analytics import record
    record(db,"lost_case_created",case.id,request=request,user=user,entity=case)
    db.commit()
    db.refresh(case)
    return case


@router.get("", response_model=list[LostCaseRead])
def list_lost_cases(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(LostCase).join(Pet).where(Pet.owner_id == user.id).order_by(LostCase.created_at.desc()).limit(limit)
    return list(db.scalars(query))


@router.get("/{case_id}", response_model=LostCaseRead)
def get_lost_case(case_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return owned_case(db, case_id, user)


@router.patch("/{case_id}", response_model=LostCaseRead)
def update_lost_case(case_id: UUID, payload: LostCaseUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    user=lock_active_user(db,user)
    case = owned_case(db, case_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") == "ACTIVE":
        require_supported_species(case.pet.species)
    for key in ("recovery_reason","recovery_match_id","recovery_observation_id"):changes.pop(key,None)
    # Owners can retire an existing notice while their email confirmation is pending.
    if set(changes) != {"status"} or changes["status"] not in {"FOUND", "CLOSED", "CANCELLED"}:
        verified_user(user)
    if changes.get("status")=="FOUND":
        from app.recovery import recover
        recover(db,case,user,reason=payload.recovery_reason,match_id=payload.recovery_match_id,
                observation_id=payload.recovery_observation_id,request=request)
        changes.pop("status")
    for field, value in changes.items():
        setattr(case, field, value)
    if "description" in changes:
        case.description_format = "USER_TEXT"
    db.flush()
    schedule_text(db, "lost_case", case.id)
    mark_related_pending(db, "lost_case", case.id)
    db.commit()
    db.refresh(case)
    return case


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lost_case(case_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    user=lock_active_user(db,user)
    case = owned_case(db, case_id, user)
    purge_owner(db, "lost_case", case_id)
    db.delete(case)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

