from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.analysis.service import purge_owner, schedule_text
from app.dependencies import current_user, verified_user
from app.models import Pet, User
from app.schemas import PetCreate, PetRead, PetUpdate
from app.matching.linked import mark_related_pending
from app.account_management import lock_active_user

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("", response_model=PetRead, status_code=status.HTTP_201_CREATED)
def create_pet(payload: PetCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    pet = Pet(owner_id=user.id, **payload.model_dump())
    db.add(pet)
    db.flush()
    from app.product_analytics import record
    record(db,"pet_created",pet.id,request=request,user=user)
    db.commit()
    db.refresh(pet)
    return pet


@router.get("", response_model=list[PetRead])
def list_pets(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list(db.scalars(select(Pet).where(Pet.owner_id == user.id).order_by(Pet.created_at.desc()).limit(limit)))


def owned_pet(db: Session, pet_id: UUID, user: User) -> Pet:
    pet = db.scalar(select(Pet).where(Pet.id == pet_id, Pet.owner_id == user.id))
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


@router.get("/{pet_id}", response_model=PetRead)
def get_pet(pet_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return owned_pet(db, pet_id, user)


@router.patch("/{pet_id}", response_model=PetRead)
def update_pet(pet_id: UUID, payload: PetUpdate, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    pet = owned_pet(db, pet_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pet, field, value)
    db.flush()
    from app.embeddings.reschedule import reschedule_owner
    reschedule_owner(db,"pet",pet.id)
    db.commit()
    db.refresh(pet)
    return pet


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pet(pet_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    user=lock_active_user(db,user)
    pet = owned_pet(db, pet_id, user)
    if pet.lost_cases:
        raise HTTPException(status_code=409, detail="A pet with lost-case history cannot be deleted")
    purge_owner(db, "pet", pet_id)
    db.delete(pet)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

