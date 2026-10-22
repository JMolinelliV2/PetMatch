"""First-party analytics. Separate savepoints ensure measurement never blocks product writes."""
import asyncio
import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from uuid import UUID, uuid4
from typing import Literal, get_args
from zoneinfo import ZoneInfo

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.analysis.service import utcnow
from app.core.config import settings
from app.matching.linked import aware
from app.models import (AnalyticsSession, AnalyticsTracking, AnalyticsVisitor, LostCase, MatchExposure, Pet, Photo,
                        ProductDaily, ProductEvent, ProductMilestone)

ZONE=ZoneInfo("America/Montevideo")
VISITOR_COOKIE="mm_visitor"
SESSION_COOKIE="mm_visit"
BrowserEventName=Literal["page_view","landing_view","registration_started","match_shown","match_viewed"]
PageCategory=Literal["HOME","REGISTER","LOGIN","LOST_CASE","MATCHES","MAP","MY_REPORTS","SIGHTING","FOUND","SUPPORT","RECOVERY","ACCOUNT","OTHER_PUBLIC"]
SERVER_EVENTS={"account_created","email_verified","pet_created","first_photo_uploaded","three_photos_uploaded",
               "five_photos_uploaded","lost_case_created","sighting_created","sighting_anonymous","sighting_authenticated",
               "sighting_linked","sighting_general","sighting_with_photo","recovery"}
PAGES=set(get_args(PageCategory))
EVENTS=SERVER_EVENTS|set(get_args(BrowserEventName))|{"session_started","returning_session"}


def digest(value):
    return hmac.new(settings.jwt_secret.encode(),("product-analytics-v1:"+value).encode(),hashlib.sha256).hexdigest()


def insert(db,model,values,*,conflict=None,increment=False):
    statement=(pg_insert if db.bind.dialect.name=="postgresql" else sqlite_insert)(model).values(**values)
    statement=statement.on_conflict_do_update(index_elements=conflict,set_={"count":model.count+1}) if increment else statement.on_conflict_do_nothing(index_elements=conflict)
    return db.execute(statement.returning(model.__table__.primary_key.columns.values()[0])).scalar_one_or_none()


def context(db,request,response=None,user=None,*,create=False):
    if not settings.analytics_enabled or request is None:return None
    now=utcnow()
    raw=request.cookies.get(VISITOR_COOKIE,"")
    valid=bool(re.fullmatch(r"[A-Za-z0-9_-]{43}",raw))
    if not valid:
        if not create:return None
        raw=secrets.token_urlsafe(32)
    identity=digest("visitor:"+raw)
    visitor=db.get(AnalyticsVisitor,identity)
    returning=visitor is not None
    if not visitor:
        if not create:return None
        insert(db,AnalyticsVisitor,{"id":identity,"first_seen_at":now,"last_seen_at":now},conflict=["id"])
        visitor=db.get(AnalyticsVisitor,identity)
    db.execute(update(AnalyticsVisitor).where(AnalyticsVisitor.id==identity,AnalyticsVisitor.last_seen_at<now).values(last_seen_at=now).execution_options(synchronize_session=False))
    signed=request.cookies.get(SESSION_COOKIE,"").split(".")
    session=None
    if len(signed)==2 and re.fullmatch(r"[a-f0-9-]{36}",signed[0]) and re.fullmatch(r"[a-f0-9]{64}",signed[1]) and hmac.compare_digest(digest("session:"+signed[0]),signed[1]):
        try:session=db.scalar(select(AnalyticsSession).where(AnalyticsSession.id==UUID(signed[0]),AnalyticsSession.visitor_id==identity).with_for_update())
        except ValueError:pass
    if not session or aware(session.last_seen_at)<=now-timedelta(minutes=settings.analytics_session_minutes):
        if not create:return None
        session=AnalyticsSession(id=uuid4(),visitor_id=identity,user_id=user.id if user else None,
            started_at=now,last_seen_at=now,returning=returning)
        db.add(session);db.flush()
        event(db,"session_started",f"session:{session.id}",session=session,user=user)
        if returning:event(db,"returning_session",f"returning:{session.id}",session=session,user=user)
    session.last_seen_at=max(aware(session.last_seen_at),now)
    if user:session.user_id=user.id
    if response is not None:
        options={"httponly":True,"secure":settings.app_env=="production","samesite":"lax","path":"/"}
        response.set_cookie(VISITOR_COOKIE,raw,max_age=settings.analytics_visitor_days*86400,**options)
        # The server, not browser expiry, enforces 30 minutes of inactivity (including backend activity).
        response.set_cookie(SESSION_COOKIE,f"{session.id}.{digest('session:'+str(session.id))}",max_age=settings.analytics_visitor_days*86400,**options)
    return session


def geography(entity=None):
    geo=getattr(entity,"analytics_geo",None) or {}
    return {"country":geo.get("country") or "ZZ","department":geo.get("department") or "unknown","locality":geo.get("locality") or "unknown"}


def event(db,name,key,*,session=None,user=None,page="OTHER_PUBLIC",geo=None,milestone=False,case_id=None):
    if name not in EVENTS or page not in PAGES:raise ValueError("Unknown product fact")
    now=utcnow();hashed=hashlib.sha256(("fact-v1:"+key).encode()).hexdigest()
    insert(db,AnalyticsTracking,{"id":1,"started_at":now},conflict=["id"])
    if milestone and not insert(db,ProductMilestone,{"key":hashed,"user_id":user.id if user else None},conflict=["key"]):return False
    geo=geo or geography()
    actor=digest("user:"+str(user.id)) if user else (session.visitor_id if session else "unknown")
    values={"id":uuid4(),"deduplication_key":hashed,"name":name,"page":page,"visitor_id":session.visitor_id if session else None,
            "session_id":session.id if session else None,"user_id":user.id if user else None,"created_at":now,"actor_key":actor,"case_id":case_id,"aggregated":False,**geo}
    if not insert(db,ProductEvent,values,conflict=["deduplication_key"]):return False
    try:
        with db.begin_nested():rollup(db,values)
    except Exception:
        from app.analysis.logging import log_event
        log_event("analytics_rollup_pending",kind=name)
    return True


def rollup(db,values):
    daily={"day":aware(values["created_at"]).astimezone(ZONE).date(),"name":values["name"],"page":values["page"],
           "visitor_id":values["visitor_id"] or "unknown","session_key":digest(str(values["session_id"])) if values["session_id"] else "unknown",
           "actor_key":values["actor_key"],"case_id":values["case_id"],
           **{key:values[key] for key in ("country","department","locality")},"count":1}
    daily["key"]=digest("|".join(str(v) for k,v in daily.items() if k!="count"))
    insert(db,ProductDaily,daily,conflict=["key"],increment=True)
    db.execute(update(ProductEvent).where(ProductEvent.id==values["id"]).values(aggregated=True))


def record(db,name,identity,*,request=None,user=None,page="OTHER_PUBLIC",entity=None):
    """Same product transaction: facts disappear if the publication/account rolls back."""
    if not settings.analytics_enabled:return
    try:
        with db.begin_nested():
            session=context(db,request,user=user)
            case_id=entity.id if isinstance(entity,LostCase) else getattr(entity,"linked_case_id",None)
            event(db,name,f"{name}:{identity}",session=session,user=user,page=page,geo=geography(entity),milestone=True,case_id=case_id)
    except Exception:
        from app.analysis.logging import log_event
        log_event("analytics_write_failed",kind=name)  # Never log identifiers, payloads or secrets.


def photo_milestones(db,photo,user,request=None):
    pet_id=photo.owner_id if photo.owner_type=="pet" else None
    if photo.owner_type=="lost_case":
        case=db.get(LostCase,photo.owner_id);pet_id=case.pet_id if case else None
    if pet_id is None:return
    cases=select(LostCase.id).where(LostCase.pet_id==pet_id)
    count=db.scalar(select(func.count()).select_from(Photo).where(or_(
        (Photo.owner_type=="pet")&(Photo.owner_id==pet_id),(Photo.owner_type=="lost_case")&Photo.owner_id.in_(cases)))) or 0
    for threshold,name in ((1,"first_photo_uploaded"),(3,"three_photos_uploaded"),(5,"five_photos_uploaded")):
        if count==threshold:record(db,name,pet_id,request=request,user=user)


def expire_rows(factory,model,column,cutoff,*extra):
    """Short independent transactions; never wait for rows owned by product requests."""
    primary=next(iter(model.__table__.primary_key.columns))
    for _ in range(50):
        with factory() as db:
            identities=list(db.scalars(select(primary).where(column<cutoff,*extra).order_by(primary)
                .limit(1000).with_for_update(skip_locked=True)))
            if not identities:return
            db.execute(delete(model).where(primary.in_(identities),*extra).execution_options(synchronize_session=False))
            db.commit()


def cleanup(factory=None):
    from app.db.session import SessionLocal
    factory=factory or SessionLocal
    now=utcnow()
    with factory() as db:
        # Multiple API workers can retry without replaying a completed aggregate.
        candidates=list(db.execute(select(ProductEvent.id,ProductEvent.case_id).where(ProductEvent.aggregated.is_(False))
                                   .order_by(ProductEvent.created_at).limit(500)))
        case_ids={case_id for _,case_id in candidates if case_id is not None}
        # Case -> event is the same order as account/publication deletion, including FK cascades.
        locked=set(db.scalars(select(LostCase.id).where(LostCase.id.in_(case_ids)).order_by(LostCase.id)
                              .with_for_update(read=True,key_share=True,skip_locked=True))) if case_ids else set()
        identities=[identity for identity,case_id in candidates if case_id is None or case_id in locked]
        pending=list(db.scalars(select(ProductEvent).where(ProductEvent.id.in_(identities),ProductEvent.aggregated.is_(False))
                                .order_by(ProductEvent.id).with_for_update(skip_locked=True)))
        failures=0
        for fact in pending:
            try:
                with db.begin_nested():
                    rollup(db,{column.name:getattr(fact,column.name) for column in ProductEvent.__table__.columns})
            except Exception:failures+=1
        if failures:
            from app.analysis.logging import log_event
            log_event("analytics_rollup_retry_failed",count=failures)
        db.commit()
    expire_rows(factory,ProductEvent,ProductEvent.created_at,now-timedelta(days=settings.analytics_raw_days))
    expired_sessions=select(AnalyticsSession.id).where(AnalyticsSession.last_seen_at<now-timedelta(days=settings.analytics_raw_days))
    # Delete children before sessions to avoid opposing FK lock order with account deletion.
    expire_rows(factory,MatchExposure,MatchExposure.shown_at,now-timedelta(days=settings.analytics_raw_days),MatchExposure.session_id.in_(expired_sessions))
    expire_rows(factory,AnalyticsSession,AnalyticsSession.last_seen_at,now-timedelta(days=settings.analytics_raw_days),
                ~exists(select(MatchExposure.id).where(MatchExposure.session_id==AnalyticsSession.id)))
    expire_rows(factory,AnalyticsVisitor,AnalyticsVisitor.last_seen_at,now-timedelta(days=settings.analytics_visitor_days),
                ~exists(select(AnalyticsSession.id).where(AnalyticsSession.visitor_id==AnalyticsVisitor.id)))
    expire_rows(factory,ProductDaily,ProductDaily.day,(now-timedelta(days=settings.analytics_daily_days)).date())


async def cleanup_loop():
    while True:
        try:await asyncio.to_thread(cleanup)
        except Exception:pass
        await asyncio.sleep(3600)
