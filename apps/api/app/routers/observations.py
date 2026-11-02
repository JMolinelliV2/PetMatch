from uuid import UUID
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.analysis.service import purge_owner, schedule_text, utcnow
from app.dependencies import current_user, verified_user
from app.models import Observation, User
from app.species import owner_is_supported, supported_observation_scope, require_supported_owner
from app.schemas import ObservationCreate, ObservationRead, ObservationUpdate, OwnedObservationRead
from app.report_text import LINKED_SIGHTING_DESCRIPTION, observation_read
from app.matching.linked import mark_related_pending, aware
from app.account_management import lock_active_user

router = APIRouter(prefix="/observations", tags=["observations"])


def owned_observation(db: Session, observation_id: UUID, user: User, lock: bool = False):
    query = select(Observation).where(Observation.id == observation_id, Observation.author_id == user.id)
    observation = db.scalar(query.with_for_update(key_share=True) if lock else query)
    if observation is None:
        raise HTTPException(status_code=404, detail="No encontramos ese reporte en tu cuenta.")
    return observation


@router.get("/{observation_id}/edit", response_model=OwnedObservationRead)
def get_owned_observation(observation_id: UUID, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    observation = owned_observation(db, observation_id, user)
    require_supported_owner(db, "observation", observation.id)
    response.headers["Cache-Control"] = "private, no-store"
    return observation


@router.post("", response_model=ObservationRead, status_code=status.HTTP_201_CREATED)
def create_observation(payload: ObservationCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    observation = Observation(author_id=user.id, **payload.model_dump())
    db.add(observation)
    db.flush()
    from app.embeddings.reschedule import reschedule_owner
    reschedule_owner(db,"observation",observation.id)
    from app.product_analytics import record
    for name in ("sighting_created","sighting_authenticated","sighting_general"):
        record(db,name,observation.id,request=request,user=user,entity=observation)
    db.commit()
    db.refresh(observation)
    return observation_read(observation)


@router.get("", response_model=list[ObservationRead])
def list_observations(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db)):
    query = select(Observation).where(supported_observation_scope(),Observation.moderation_status=="VISIBLE").order_by(Observation.created_at.desc()).limit(limit)
    return [observation_read(item) for item in db.scalars(query)]


@router.get("/{observation_id}", response_model=ObservationRead)
def get_observation(observation_id: UUID, db: Session = Depends(get_db)):
    observation = db.get(Observation, observation_id)
    if observation is None or not owner_is_supported(db,"observation",observation_id) or observation.moderation_status!="VISIBLE":
        raise HTTPException(status_code=404, detail="Observation not found")
    return observation_read(observation)


@router.patch("/{observation_id}", response_model=ObservationRead)
def update_observation(observation_id: UUID, payload: ObservationUpdate, db: Session = Depends(get_db), user: User = Depends(verified_user)):
    user=lock_active_user(db,user)
    observation = owned_observation(db, observation_id, user, lock=True)
    require_supported_owner(db, "observation", observation.id)
    changes = payload.model_dump(exclude_unset=True)
    if "description" in changes:
        if changes["description"] is None:
            raise HTTPException(status_code=422, detail="Ingresá una descripción del reporte.")
        changes["description"] = changes["description"].strip()
        if not changes["description"]:
            if not observation.linked_case_id:
                raise HTTPException(status_code=422, detail="Ingresá una descripción del reporte.")
            changes["description"] = LINKED_SIGHTING_DESCRIPTION
            changes["description_format"] = "SYSTEM"
        else:
            changes["description_format"] = "USER_TEXT"
    when = changes.get("observed_at", observation.observed_at)
    if when is None or aware(when) > utcnow() + timedelta(minutes=1):
        raise HTTPException(status_code=422, detail="Ingresá una fecha y hora válidas, que no estén en el futuro.")
    latitude = changes.get("latitude", observation.latitude)
    longitude = changes.get("longitude", observation.longitude)
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="La ubicación necesita un punto completo.")
    if observation.linked_case_id and latitude is None:
        raise HTTPException(status_code=422, detail="El avistamiento vinculado necesita una ubicación.")
    for field, value in changes.items():
        setattr(observation, field, value)
    db.flush()
    from app.embeddings.reschedule import reschedule_owner
    reschedule_owner(db,"observation",observation.id)
    db.commit()
    db.refresh(observation)
    return observation_read(observation)


@router.delete("/{observation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_observation(observation_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    user=lock_active_user(db,user)
    observation = db.get(Observation, observation_id)
    if observation is None or observation.author_id != user.id:
        raise HTTPException(status_code=404, detail="Observation not found")
    purge_owner(db, "observation", observation_id)
    db.delete(observation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

