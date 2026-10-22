"""Signed server presentation receipts. Fetching a recommendation is not a view."""
import base64
import hmac
import json
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.analysis.service import utcnow
from app.models import LostCase, Match, MatchExposure, Pet
from app.product_analytics import context, digest, event, geography, insert


def presentation(match,user,rank,context_name="LOST_CASE"):
    payload={"match":str(match.id),"owner":str(user.id),"rank":rank,"context":context_name,
             "issued":int(utcnow().timestamp()),"score":match.final_score}
    encoded=base64.urlsafe_b64encode(json.dumps(payload,separators=(",",":")).encode()).decode().rstrip("=")
    return encoded+"."+digest("presentation:"+encoded)


def receipt(value,user):
    try:
        encoded,signature=value.split(".")
        if not hmac.compare_digest(digest("presentation:"+encoded),signature):raise ValueError()
        data=json.loads(base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)))
        if data["owner"]!=str(user.id) or not 0<=utcnow().timestamp()-data["issued"]<=7200:raise ValueError()
        if data["context"] not in {"LOST_CASE","NOTIFICATION"} or not 1<=data["rank"]<=100:raise ValueError()
        UUID(data["match"])
        return data
    except (ValueError,KeyError,TypeError):raise HTTPException(422,"La referencia de la coincidencia venció. Actualizá la lista.")


def expose(db,request,response,user,token,stage):
    data=receipt(token,user)
    case=db.scalar(select(LostCase).join(Match,Match.lost_case_id==LostCase.id).join(Pet,LostCase.pet_id==Pet.id)
        .where(Match.id==UUID(data["match"]),Pet.owner_id==user.id).with_for_update(of=LostCase))
    if case is None:raise HTTPException(404,"Coincidencia no encontrada.")
    match=db.scalar(select(Match).where(Match.id==UUID(data["match"])).with_for_update())
    if match.recommended_at is None:raise HTTPException(422,"Este reporte no es una recomendación automática.")
    session=context(db,request,response,user,create=True)
    now=utcnow()
    insert(db,MatchExposure,{"id":uuid4(),"session_id":session.id,"match_id":match.id,"context":data["context"],
        "rank":data["rank"],"shown_at":now,"viewed_at":None},conflict=["session_id","match_id","context"])
    exposure=db.scalar(select(MatchExposure).where(MatchExposure.session_id==session.id,MatchExposure.match_id==match.id,
                                                  MatchExposure.context==data["context"]).with_for_update())
    match.first_shown_at=match.first_shown_at or now
    if stage=="viewed" and exposure.viewed_at is None:
        exposure.rank=data["rank"]
        exposure.viewed_at=now
        if match.first_viewed_at is None:
            match.first_viewed_at=now
            match.viewed_snapshot={"context":data["context"],"rank":exposure.rank,"score":data["score"],
                                   "recommendation":match.recommendation_snapshot}
        # Top-K only applies to the ranked case list, never a single notification detail.
        if data["context"]=="LOST_CASE":
            match.first_viewed_rank=match.first_viewed_rank or exposure.rank
            match.best_viewed_rank=min(match.best_viewed_rank or exposure.rank,exposure.rank)
        event(db,"match_viewed",f"view:{session.id}:{match.id}:{data['context']}",session=session,user=user,page="MATCHES",geo=geography(case),case_id=case.id)
    if stage=="viewed" and data["context"]=="LOST_CASE":
        match.best_viewed_rank=min(match.best_viewed_rank or data["rank"],data["rank"])
    event(db,"match_shown",f"shown:{session.id}:{match.id}:{data['context']}",session=session,user=user,page="MATCHES",geo=geography(case),case_id=case.id)

