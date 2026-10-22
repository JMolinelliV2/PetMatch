from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy import select
from app.db.session import get_db
from app.dependencies import current_user,verified_user
from app.models import LostCase, Observation, Pet
from app.schemas import LostCaseRead, PetRead, ObservationRead, CaseEdit
from app.routers.lost_cases import owned_case
from app.analysis.service import schedule_text
from app.matching.linked import mark_related_pending
router=APIRouter(tags=["dashboard"])


@router.get("/me/dashboard")
def dashboard(response: Response,db=Depends(get_db),user=Depends(current_user)):
    response.headers["Cache-Control"]="no-store"
    pets=list(db.scalars(select(Pet).where(Pet.owner_id==user.id).order_by(Pet.created_at.desc())))
    cases=list(db.scalars(select(LostCase).join(Pet).where(Pet.owner_id==user.id).order_by(LostCase.created_at.desc())))
    observations=list(db.scalars(select(Observation).where(Observation.author_id==user.id).order_by(Observation.created_at.desc())))
    return {"pets":[PetRead.model_validate(item) for item in pets],"cases":[LostCaseRead.model_validate(item) for item in cases],
        "observations":[ObservationRead.model_validate(item) for item in observations]}


@router.patch("/me/cases/{case_id}",response_model=LostCaseRead)
def edit_case(case_id:UUID,payload:CaseEdit,response:Response,request:Request,db=Depends(get_db),user=Depends(verified_user)):
    case=owned_case(db,case_id,user)
    pet=db.get(Pet,case.pet_id)
    for field,value in payload.pet.model_dump(exclude_unset=True).items():
        setattr(pet,field,value)
    changes=payload.case.model_dump(exclude_unset=True)
    for key in ("recovery_reason","recovery_match_id","recovery_observation_id"):changes.pop(key,None)
    if changes.get("status")=="FOUND":
        from app.recovery import recover
        recover(db,case,user,reason=payload.case.recovery_reason,match_id=payload.case.recovery_match_id,
                observation_id=payload.case.recovery_observation_id,request=request)
        changes.pop("status")
    for field,value in changes.items():
        setattr(case,field,value)
    if (case.latitude is None)!=(case.longitude is None):
        raise HTTPException(status_code=422,detail="La ubicación necesita un punto completo.")
    db.flush()
    from app.embeddings.reschedule import reschedule_owner
    reschedule_owner(db,"pet",pet.id)
    db.commit()
    response.headers["Cache-Control"]="no-store"
    return case
