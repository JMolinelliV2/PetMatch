"""One consistent owner recovery transition, shared by every mutation path."""
from fastapi import HTTPException
from sqlalchemy import select, update
from app.analysis.service import utcnow
from app.models import Match, Notification, Observation, RecoveryOutcome
from app.product_analytics import record


def recover(db,case,user,*,reason="PREFER_NOT_TO_SAY",match_id=None,observation_id=None,request=None):
    # Callers lock the case before any match, matching notification delivery's lock order.
    existing=db.get(RecoveryOutcome,case.id)
    if case.status=="FOUND":return existing  # Legacy FOUND stays unknown; retries cannot invent attribution.
    if case.status!="ACTIVE":raise HTTPException(409,"La búsqueda ya está cerrada.")
    match=db.get(Match,match_id) if match_id else None
    if match_id and (not match or match.lost_case_id!=case.id):raise HTTPException(422,"La coincidencia no corresponde a este aviso.")
    if match and reason in {"MASCOMATCH_MATCH","MASCOMATCH_SIGHTING"}:observation_id=match.observation_id
    observation=db.get(Observation,observation_id) if observation_id else None
    if observation_id and (not observation or (observation.linked_case_id!=case.id and not db.scalar(select(Match.id).where(Match.lost_case_id==case.id,Match.observation_id==observation_id)))):
        raise HTTPException(422,"El avistamiento no corresponde a este aviso.")
    case.status="FOUND"
    if existing is None:
        existing=RecoveryOutcome(lost_case_id=case.id,owner_id=user.id,reason=reason,
            match_id=match_id if reason=="MASCOMATCH_MATCH" else None,
            observation_id=observation_id if reason in {"MASCOMATCH_MATCH","MASCOMATCH_SIGHTING"} else None,recovered_at=utcnow())
        db.add(existing)
        record(db,"recovery",case.id,request=request,user=user,page="RECOVERY",entity=case)
    db.execute(update(Match).where(Match.lost_case_id==case.id).values(is_active=False))
    db.execute(update(Notification).where(Notification.lost_case_id==case.id).values(is_active=False))
    db.execute(update(Notification).where(Notification.lost_case_id==case.id,Notification.email_status=="PENDING").values(email_status="CANCELLED"))
    return existing
