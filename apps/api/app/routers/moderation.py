from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Response,Query
from pydantic import BaseModel,ConfigDict,Field
from pydantic import AwareDatetime
from sqlalchemy import func,select
from app.admin_period import period_filters
from app.db.session import get_db
from app.dependencies import optional_user
from app.models import AdminAudit,CaseReview,LostCase,ModerationReport,Observation,Pet,User,Notification,AnalysisJob,Match,Photo
from app.matching.linked import mark_related_pending
from app.admin_access import administrator as admin
from app.admin_moderation import publication_author, set_account_status, set_visibility
router=APIRouter(tags=["moderation"])


class ReportInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    target_type:Literal["lost_case","observation"]
    target_id:UUID
    reason:Literal["SPAM","FALSE_INFORMATION","INAPPROPRIATE_PHOTO","OTHER"]
    detail:str=Field(default="",max_length=1000)


class ReviewInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    action:Literal["DISMISS","HIDE","RESTORE","BLOCK_AUTHOR"]


class CorrectionInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    description:str=Field(min_length=1,max_length=4000)


class UserStatusInput(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    status:Literal["ACTIVE","BLOCKED"]
    reason:str=Field(default="",max_length=1000)


class VisibilityInput(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    status:Literal["VISIBLE","HIDDEN"]
    reason:str=Field(min_length=3,max_length=1000)


@router.post("/reports",status_code=201)
def create_report(payload:ReportInput,db=Depends(get_db),user=Depends(optional_user)):
    target=db.get(LostCase if payload.target_type=="lost_case" else Observation,payload.target_id)
    if target is None or target.moderation_status!="VISIBLE":raise HTTPException(status_code=404,detail="Publicación no encontrada.")
    report=ModerationReport(reporter_id=user.id if user else None,**payload.model_dump())
    db.add(report);db.commit()
    return {"id":report.id,"status":report.status}


@router.get("/admin/reports")
def reports(response:Response,status:Literal["OPEN","ACTION_TAKEN","DISMISSED",""]="OPEN",
            from_at:AwareDatetime|None=None,to_at:AwareDatetime|None=None,
            limit:int=Query(default=25,ge=1,le=100),offset:int=Query(default=0,ge=0,le=100000),db=Depends(get_db),user=Depends(admin)):
    response.headers["Cache-Control"]="no-store"
    query=select(ModerationReport).where(*period_filters(ModerationReport.created_at,from_at,to_at)).order_by(ModerationReport.created_at.desc(),ModerationReport.id)
    if status:query=query.where(ModerationReport.status==status)
    items=[]
    total=db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    for report in db.scalars(query.offset(offset).limit(limit)):
        target=db.get(LostCase if report.target_type=="lost_case" else Observation,report.target_id)
        pet=db.get(Pet,target.pet_id) if isinstance(target,LostCase) else None
        title=pet.name if pet else "Avistamiento" if target else "Publicación eliminada"
        items.append({"id":report.id,"target_type":report.target_type,"target_id":report.target_id,"public_id":target.public_id if target else None,"title":title,"reason":report.reason,"detail":report.detail,"status":report.status,"created_at":report.created_at,"visibility":target.moderation_status if target else None})
        if target:
            from sqlalchemy import and_,or_
            scope=Photo.owner_id==target.id
            scope=or_(and_(Photo.owner_type=="lost_case",Photo.owner_id==target.id),and_(Photo.owner_type=="pet",Photo.owner_id==target.pet_id)) if isinstance(target,LostCase) else and_(Photo.owner_type=="observation",Photo.owner_id==target.id)
            items[-1]["publication"]={"description":target.description,"photo_ids":list(db.scalars(select(Photo.id).where(scope)))}
    return {"items":items,"total":total,"limit":limit,"offset":offset}


@router.patch("/admin/reports/{report_id}")
def review(report_id:UUID,payload:ReviewInput,db=Depends(get_db),user=Depends(admin)):
    report=db.scalar(select(ModerationReport).where(ModerationReport.id==report_id).with_for_update())
    if report is None:raise HTTPException(status_code=404,detail="Denuncia no encontrada.")
    target=db.get(LostCase if report.target_type=="lost_case" else Observation,report.target_id)
    if payload.action!="DISMISS" and target is None:raise HTTPException(status_code=404,detail="Publicación no encontrada.")
    if payload.action=="DISMISS":report.status="DISMISSED"
    else:
        if payload.action=="BLOCK_AUTHOR":
            author_id=publication_author(db,target)
            if author_id:
                set_account_status(db,author_id,"BLOCKED",user.id)
            else:raise HTTPException(status_code=409,detail="Este reporte no tiene una cuenta asociada. Podés ocultarlo.")
        else:
            set_visibility(db,report.target_type,target.id,"VISIBLE" if payload.action=="RESTORE" else "HIDDEN")
        report.status="ACTION_TAKEN"
    db.add(AdminAudit(actor_id=user.id,action=payload.action,target_type=report.target_type,target_id=report.target_id,report_id=report.id,details={"reason":f"Denuncia: {report.reason}"}))
    db.commit()
    return {"id":report.id,"status":report.status}


@router.get("/admin/overview")
def overview(response:Response,db=Depends(get_db),user=Depends(admin)):
    from sqlalchemy import func
    response.headers["Cache-Control"]="no-store"
    counts={model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in (User,Pet,LostCase,Observation,Match,ModerationReport,CaseReview)}
    failures=[{"id":job.id,"source":job.source_type,"error_code":job.error_code,"finished_at":job.finished_at} for job in db.scalars(select(AnalysisJob).where(AnalysisJob.status=="FAILED").order_by(AnalysisJob.finished_at.desc()).limit(50))]
    audits=[{"action":item.action,"target_type":item.target_type,"target_id":item.target_id,"created_at":item.created_at} for item in db.scalars(select(AdminAudit).order_by(AdminAudit.created_at.desc()).limit(50))]
    return {"counts":counts,"ai_failures":failures,"audit":audits}


@router.get("/admin/records/{kind}")
def records(kind:Literal["users","pets","lost_cases","observations","matches","reviews"],response:Response,limit:int=Query(default=50,ge=1,le=100),offset:int=Query(default=0,ge=0,le=10000),db=Depends(get_db),user=Depends(admin)):
    config={"users":(User,["id","name","status","role"]),"pets":(Pet,["id","name","species","owner_id"]),
        "lost_cases":(LostCase,["id","status","moderation_status","description","pet_id"]),"observations":(Observation,["id","source_type","moderation_status","description","author_id"]),
        "matches":(Match,["id","status","lost_case_id","observation_id","final_score","explanation"]),
        "reviews":(CaseReview,["id","display_name","rating","comment","visibility","created_at"])}
    model,fields=config[kind]
    response.headers["Cache-Control"]="no-store"
    return {"items":[{field:getattr(item,field) for field in fields} for item in db.scalars(select(model).order_by(model.created_at.desc()).offset(offset).limit(limit))]}


@router.patch("/admin/publications/{kind}/{identity}")
def correct(kind:Literal["lost_case","observation"],identity:UUID,payload:CorrectionInput,db=Depends(get_db),user=Depends(admin)):
    target=db.get(LostCase if kind=="lost_case" else Observation,identity)
    if target is None:raise HTTPException(status_code=404,detail="Publicación no encontrada.")
    previous=target.description;target.description=payload.description;target.description_format="USER_TEXT"
    db.add(AdminAudit(actor_id=user.id,action="CORRECT_DESCRIPTION",target_type=kind,target_id=identity,details={"previous_description":previous,"new_description":payload.description}))
    db.flush()
    from app.analysis.service import schedule_text
    schedule_text(db,kind,identity);mark_related_pending(db,kind,identity);db.commit()
    return {"id":target.id,"description":target.description}


@router.patch("/admin/users/{identity}/status")
def user_status(identity:UUID,payload:UserStatusInput,db=Depends(get_db),user=Depends(admin)):
    target,previous=set_account_status(db,identity,payload.status,user.id)
    db.add(AdminAudit(actor_id=user.id,action="BLOCK_USER" if payload.status=="BLOCKED" else "UNBLOCK_USER",target_type="user",target_id=identity,details={"previous_status":previous,"status":payload.status,"reason":payload.reason.strip()}))
    db.commit();return {"id":target.id,"status":target.status}


@router.patch("/admin/publications/{kind}/{identity}/visibility")
def publication_visibility(kind:Literal["lost_case","observation"],identity:UUID,payload:VisibilityInput,db=Depends(get_db),user=Depends(admin)):
    target,previous=set_visibility(db,kind,identity,payload.status)
    db.add(AdminAudit(actor_id=user.id,action="HIDE_PUBLICATION" if payload.status=="HIDDEN" else "RESTORE_PUBLICATION",target_type=kind,target_id=identity,details={"previous_status":previous,"status":payload.status,"reason":payload.reason.strip()}))
    db.commit()
    return {"id":target.id,"public_id":target.public_id,"status":target.moderation_status}


@router.get("/admin/reports/{report_id}/photos/{photo_id}")
def report_photo(report_id:UUID,photo_id:UUID,db=Depends(get_db),user=Depends(admin)):
    from sqlalchemy import and_,or_
    from app.core.image_storage import load_analysis_image
    report=db.get(ModerationReport,report_id)
    target=db.get(LostCase if report and report.target_type=="lost_case" else Observation,report.target_id) if report else None
    if target is None:raise HTTPException(status_code=404,detail="Publicación no encontrada.")
    scope=or_(and_(Photo.owner_type=="lost_case",Photo.owner_id==target.id),and_(Photo.owner_type=="pet",Photo.owner_id==target.pet_id)) if isinstance(target,LostCase) else and_(Photo.owner_type=="observation",Photo.owner_id==target.id)
    photo=db.scalar(select(Photo).where(Photo.id==photo_id,scope))
    if photo is None:raise HTTPException(status_code=404,detail="Foto no encontrada.")
    try:payload,mime=load_analysis_image(photo.storage_key,photo.mime_type)
    except Exception as exc:raise HTTPException(status_code=503,detail="La foto no está disponible.") from exc
    return Response(payload,media_type=mime,headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
