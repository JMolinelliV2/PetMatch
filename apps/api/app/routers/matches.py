from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import exists, select, update
from app.analysis.service import utcnow, is_current, schedule_owner
from app.core.config import settings
from app.db.session import get_db
from app.dependencies import current_user,verified_user
from app.models import AnalysisJob, LostCase, Match, Notification, Observation, Pet, Photo
from app.routers.lost_cases import owned_case
from app.routers.public_lost_dogs import notice, photo_scope
from app.schemas import MatchRead, MatchFeedback
from app.matching.tracking import record_feedback
from app.matching.visibility import presentation
from app.services.access import owner_has_access

router = APIRouter(tags=["matches"])


@router.get("/matches/observations/{observation_id}")
def observation_matches(observation_id: UUID, response: Response, db=Depends(get_db), user=Depends(current_user)):
    observation = db.get(Observation, observation_id)
    if observation is None or observation.author_id != user.id:
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")
    response.headers["Cache-Control"] = "no-store"
    rows = db.execute(select(Match, LostCase, Pet).join(LostCase, Match.lost_case_id == LostCase.id).join(Pet, LostCase.pet_id == Pet.id).where(
        Match.observation_id == observation_id, Match.is_active.is_(True), LostCase.status == "ACTIVE", Match.status.not_in(["FALSE_MATCH", "RESOLVED"]),
        observation.linked_case_id is None or observation.matching_status == "POSSIBLE_MATCH").order_by(Match.final_score.desc(), Match.id).limit(50))
    return {"status": observation.matching_status, "items": [{"match": MatchRead.model_validate(match), "animal": notice(case, pet,
        db.scalar(select(Photo.id).where(photo_scope(case)).limit(1)) is not None)} for match,case,pet in rows]}


@router.get("/matches/lost-cases/{case_id}")
def case_matches(case_id: UUID, response: Response, db=Depends(get_db), user=Depends(current_user)):
    owned_case(db, case_id, user)
    response.headers["Cache-Control"] = "no-store"
    has_photo = exists().where(Photo.owner_type == "observation", Photo.owner_id == Observation.id).correlate(Observation)
    rows = db.execute(select(Match, Observation, has_photo).join(Observation, Match.observation_id == Observation.id).where(
        Match.lost_case_id == case_id, Match.is_active.is_(True), Observation.moderation_status == "VISIBLE").order_by((Observation.linked_case_id == case_id).desc().nullslast(), Observation.observed_at.desc(), Match.final_score.desc(), Match.id).limit(100))
    return {"items": [{"match": MatchRead.model_validate(match).model_copy(update={"presentation":presentation(match,user,rank) if match.recommended_at else None}), "observation": {"id": observation.id, "public_id": observation.public_id, "description": observation.description,
        "observed_at": observation.observed_at, "public_location": observation.public_location, "latitude":observation.latitude,"longitude":observation.longitude,
        "source_type":observation.source_type,"photo_url":f"/api/v1/public/observations/{observation.id}/photo" if photo else None,
        "matching_status":observation.matching_status,"linked_to_notice":observation.linked_case_id==case_id}} for rank,(match, observation, photo) in enumerate(rows,1)]}


@router.patch("/matches/{match_id}/feedback", response_model=MatchRead)
def feedback(match_id: UUID, payload: MatchFeedback, response: Response, request: Request, db=Depends(get_db), user=Depends(current_user)):
    # Lock the owned case before its matches, as notification delivery does.
    case = db.scalar(select(LostCase).join(Match, Match.lost_case_id == LostCase.id).join(Pet, LostCase.pet_id == Pet.id).where(Match.id == match_id, Pet.owner_id == user.id).with_for_update(of=LostCase))
    if case is None:
        raise HTTPException(status_code=404, detail="Coincidencia no encontrada.")
    match = db.scalar(select(Match).where(Match.id == match_id, Match.lost_case_id == case.id).with_for_update())
    if match is None:
        raise HTTPException(status_code=404, detail="Coincidencia no encontrada.")
    if payload.recovered and case.status not in {"ACTIVE", "FOUND"}:
        raise HTTPException(status_code=409, detail="La búsqueda ya está cerrada. Revisá el estado en Mis avisos.")
    if payload.recovery_match_id and payload.recovery_match_id!=match.id:
        raise HTTPException(422,"La coincidencia no corresponde a esta respuesta.")
    already_recovered=case.status=="FOUND"
    changed=record_feedback(db, match, user, payload,already_recovered=already_recovered)
    match.status=payload.status
    if changed:match.feedback_at=utcnow()
    if payload.recovered:
        from app.recovery import recover
        recover(db,case,user,reason=payload.recovery_reason,match_id=match.id,
                observation_id=payload.recovery_observation_id,request=request)
    elif payload.status == "FALSE_MATCH":
        for notification in db.scalars(select(Notification).where(Notification.match_id == match.id)):
            notification.is_active = False
    elif payload.status == "RESOLVED":
        for notification in db.scalars(select(Notification).where(Notification.match_id == match.id)):
            notification.read_at = notification.read_at or utcnow()
            if notification.email_status == "PENDING":
                notification.email_status = "CANCELLED"
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return match


@router.get("/embeddings/{owner_type}/{owner_id}")
def embedding_status(owner_type: Literal["pet", "lost_case", "observation"], owner_id: UUID, response: Response, db=Depends(get_db), user=Depends(current_user)):
    if not owner_has_access(owner_type, owner_id, db, user):
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")
    jobs = [job for job in db.scalars(select(AnalysisJob).where(AnalysisJob.owner_type == owner_type, AnalysisJob.owner_id == owner_id,
        AnalysisJob.source_type == "embedding")) if is_current(db,job)]
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": settings.embeddings_enabled, "model": jobs[0].model if jobs else None, "dimension": 512,
        "jobs": [{"id":job.id,"status":job.status,"error_code":job.error_code,"photo_id":job.photo_id,
                  "provider":job.provider,"model":job.model} for job in jobs]}


@router.post("/embeddings/{owner_type}/{owner_id}", status_code=202)
def start_embeddings(owner_type: Literal["pet", "lost_case", "observation"], owner_id: UUID, response: Response, db=Depends(get_db), user=Depends(verified_user)):
    if not owner_has_access(owner_type,owner_id,db,user):
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")
    if not settings.embeddings_enabled:
        raise HTTPException(status_code=409, detail="El análisis visual está deshabilitado.")
    schedule_owner(db,owner_type,owner_id)
    from app.matching.engine import request_matching
    request_matching(db,owner_type,owner_id)
    db.commit()
    return embedding_status(owner_type,owner_id,response,db,user)
