from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from app.core.config import settings
from app.db.session import get_db
from app.dependencies import optional_user
from app.models import LostCase
from app.product_analytics import BrowserEventName, PageCategory, context, event, geography

router=APIRouter(prefix="/analytics",tags=["analytics"])


class BrowserEvent(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: BrowserEventName
    page: PageCategory
    event_id: UUID
    entity_id: UUID | None=None
    presentation: str | None=Field(default=None,max_length=1800)


@router.post("/events",status_code=204)
def collect(payload:BrowserEvent,request:Request,response:Response,db=Depends(get_db),user=Depends(optional_user)):
    response.headers["Cache-Control"]="no-store"
    if request.headers.get("origin","").rstrip("/")!=settings.web_origin.rstrip("/"):
        raise HTTPException(403,"Origen no permitido.")
    agent=request.headers.get("user-agent","").lower()
    prefetch=request.headers.get("purpose")=="prefetch" or request.headers.get("next-router-prefetch")=="1" or "prefetch" in request.headers.get("sec-purpose","")
    if not settings.analytics_enabled or prefetch or request.headers.get("x-mascomatch-synthetic")=="1" or any(word in agent for word in ("bot","crawler","spider","headless","prometheus","smoke")):
        return
    if payload.name.startswith("match_"):
        if not user:raise HTTPException(401,"Iniciá sesión.")
        if not payload.presentation:raise HTTPException(422,"Falta la referencia de presentación.")
        from app.matching.visibility import expose
        expose(db,request,response,user,payload.presentation,"viewed" if payload.name=="match_viewed" else "shown")
    else:
        if payload.name=="landing_view" and payload.page!="HOME" or payload.name=="registration_started" and payload.page!="REGISTER":
            raise HTTPException(422,"Evento fuera de contexto.")
        entity=None
        if payload.page in {"LOST_CASE","RECOVERY"} and payload.entity_id is None:
            raise HTTPException(422,"Falta el contexto del aviso.")
        if payload.page in {"LOST_CASE","RECOVERY"} and payload.entity_id:
            entity=db.scalar(select(LostCase).where(LostCase.id==payload.entity_id).with_for_update(read=True,key_share=True))
            if entity is None or entity.moderation_status!="VISIBLE":raise HTTPException(404,"Aviso no encontrado.")
            if payload.page=="LOST_CASE" and (entity.status!="ACTIVE" or entity.pet.owner.status!="ACTIVE"):
                raise HTTPException(404,"Aviso no encontrado.")
            if payload.page=="RECOVERY" and (not user or entity.pet.owner_id!=user.id or entity.status!="FOUND"):
                raise HTTPException(404,"Experiencia no disponible.")
        session=context(db,request,response,user,create=True)
        key=f"browser:{session.id}:{payload.name}:{payload.event_id}"
        if payload.name=="registration_started":key=f"registration:{session.id}"
        event(db,payload.name,key,session=session,user=user,page=payload.page,geo=geography(entity),case_id=entity.id if entity else None)
    db.commit()
