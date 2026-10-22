"""Private product/impact analytics over existing operational and recommendation truth."""
from collections import defaultdict
import csv
import hashlib
import io
import json
from datetime import timedelta
from statistics import median
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.encoders import jsonable_encoder
from redis import Redis
from pydantic import AwareDatetime
from sqlalchemy import and_, case, exists, func, select

from app.admin_access import administrator
from app.admin_period import period_filters
from app.analysis.service import utcnow
from app.core.config import settings
from app.db.session import get_db
from app.matching.linked import aware
from app.models import (AnalysisJob, AnalyticsTracking, LostCase, Match, MatchFeedbackEvent, Observation,
                        Pet, Photo, ProductDaily, ProductEvent, RecoveryOutcome, User, UserActivity)
from app.product_analytics import ZONE
from app.routers.admin_matching import counters, outcome, scope

router=APIRouter(prefix="/admin/analytics",tags=["admin-analytics"])
SAMPLE_LIMIT=10000
CACHE_SECONDS=60


def cached_dashboard(section,fingerprint,data=None):
    """At most five 512 KB keys in the existing Redis, never an unbounded filter cache."""
    if settings.app_env!="production":return None
    try:
        with Redis.from_url(settings.redis_url,socket_connect_timeout=.25,socket_timeout=.25) as redis:
            key="mascomatch:analytics:dashboard:v1:"+section
            if data is None:
                raw=redis.get(key)
                cached=json.loads(raw) if raw and len(raw)<=524288 else None
                return cached["data"] if cached and cached.get("fingerprint")==fingerprint else None
            payload=json.dumps({"fingerprint":fingerprint,"data":jsonable_encoder(data)},separators=(",",":"),allow_nan=False)
            if len(payload.encode())<=524288:redis.set(key,payload,ex=CACHE_SECONDS)
    except Exception:pass
    return None


def percent(part,total):return round(100*part/total,2) if total else None


def distribution(values):
    values=sorted(value for value in values if value is not None and value>=0)
    return {"n":len(values),"p50_seconds":round(median(values),2) if values else None,
            "p95_seconds":round(values[max(0,int(.95*len(values)+.999)-1)],2) if len(values)>=20 else None}


def count(db,model,*filters):return db.scalar(select(func.count()).select_from(model).where(*filters)) or 0


def metric(label,value,help,unit=""):
    return {"label":label,"value":value,"help":help,"unit":unit}


def bucket(db,column,group,*,date_only=False):
    if db.bind.dialect.name=="postgresql":
        local=column if date_only else func.timezone("America/Montevideo",column)
        return func.to_char(func.date_trunc(group,local),"YYYY-MM-DD")
    local=column if date_only else func.datetime(column,"-3 hours")
    if group=="month":return func.strftime("%Y-%m-01",local)
    if group=="week":return func.date(local,"-"+func.cast((func.cast(func.strftime("%w",local),__import__('sqlalchemy').Integer)+6)%7,__import__('sqlalchemy').String)+" days")
    return func.date(local)


def product_source(db,from_at,to_at):
    # Raw events support exact hour filters. Older history uses daily aggregates with explicit precision.
    raw=from_at is not None and from_at>=utcnow()-timedelta(days=settings.analytics_raw_days)
    model=ProductEvent if raw else ProductDaily
    column=model.created_at if raw else model.day
    lower=from_at if raw else from_at.astimezone(ZONE).date() if from_at else None
    upper=to_at if raw else to_at.astimezone(ZONE).date()+timedelta(days=1) if to_at else None
    return model,period_filters(column,lower,upper),"event" if raw else "day"


def product(db,from_at,to_at,group,event_names=None):
    model,filters,precision=product_source(db,from_at,to_at)
    if event_names:filters.append(model.name.in_(event_names))
    amount=func.count() if model is ProductEvent else func.sum(model.count)
    rows=db.execute(select(model.name,amount,func.count(func.distinct(model.actor_key)),
        func.count(func.distinct(func.nullif(model.visitor_id,"unknown")))).where(*filters).group_by(model.name))
    facts={name:{"total":total,"actors":actors,"visitors":visitors} for name,total,actors,visitors in rows}
    date=bucket(db,model.created_at if model is ProductEvent else model.day,group,date_only=model is ProductDaily)
    series=[{"date":day,"name":name,"value":value} for day,name,value in db.execute(
        select(date,model.name,amount).where(*filters).group_by(date,model.name).order_by(date))]
    return model,filters,amount,facts,series,precision


def growth(db,facts):
    number=lambda name,field="total":facts.get(name,{}).get(field,0)
    metrics=[metric("Visitantes únicos",number("page_view","visitors"),"Navegadores seudónimos distintos con una vista de página. Dos dispositivos pueden contar como dos visitantes."),
        metric("Sesiones",number("session_started"),"Nueva visita o más de 30 minutos sin actividad registrada."),
        metric("Vistas de página",number("page_view"),"Navegaciones reales visibles; no solicitudes de API, prefetch ni tareas automáticas."),
        metric("Visitantes que volvieron",number("returning_session","visitors"),"Visitantes ya observados antes del inicio de una nueva sesión. No es una métrica de retención por cohortes.")]
    funnel=[];previous=None;landing=number("landing_view","visitors")
    for name in ("landing_view","registration_started","account_created","email_verified","pet_created","first_photo_uploaded","three_photos_uploaded","five_photos_uploaded"):
        value=number(name,"visitors" if name in {"landing_view","registration_started"} else "actors")
        funnel.append({"event":name,"people":value,"total_events":number(name),"previous_percent":percent(value,previous) if previous is not None else None,
                       "landing_percent":percent(value,landing)})
        previous=value
    return metrics,{"funnel":funnel,"funnel_note":"Conversión de volúmenes en el período, no una cohorte cerrada: las cuentas pueden haber visitado antes o desde otro dispositivo. Los primeros pasos cuentan navegadores; los siguientes, usuarios distintos. No sumar mascotas como personas."}


def usage(db,from_at,to_at):
    now=utcnow();midnight=now.astimezone(ZONE).replace(hour=0,minute=0,second=0,microsecond=0)
    activity_help="Usuarios autenticados distintos según UserActivity. Incluye solicitudes automáticas de la aplicación; no significa atención continua. Ventana actual independiente del filtro de publicaciones."
    metrics=[metric(label,db.scalar(select(func.count(func.distinct(UserActivity.user_id))).where(UserActivity.occurred_at>=start)) or 0,activity_help)
             for label,start in (("DAU",midnight),("WAU",now-timedelta(days=7)),("MAU",now-timedelta(days=30)))]
    definitions=[("Cuentas",User,[]),("Cuentas verificadas",User,[User.email_verified_at.is_not(None)]),
        ("Mascotas creadas",Pet,[]),("Búsquedas creadas",LostCase,[]),("Búsquedas activas",LostCase,[LostCase.status=="ACTIVE"]),
        ("Búsquedas recuperadas",LostCase,[LostCase.status=="FOUND"]),("Búsquedas cerradas",LostCase,[LostCase.status.in_(["CLOSED","CANCELLED"])])]
    for label,model,extra in definitions:
        metrics.append(metric(label,count(db,model,*period_filters(model.created_at,from_at,to_at),*extra),"Registros existentes creados en el período; incluye historia previa. El estado es el actual."))
    metrics.extend([
        metric("Fotos cargadas",count(db,Photo,*period_filters(Photo.created_at,from_at,to_at)),"Registros de fotos existentes creados en el período."),
        metric("Recomendaciones generadas",count(db,Match,Match.recommended_at.is_not(None),*period_filters(Match.recommended_at,from_at,to_at)),"Parejas únicas por fecha de primera recomendación."),
        metric("Coincidencias con primera vista",count(db,Match,Match.recommended_at.is_not(None),Match.first_viewed_at.is_not(None),*period_filters(Match.first_viewed_at,from_at,to_at)),"Coincidencias distintas cuya primera vista ocurrió en el período. No suma todas las sesiones repetidas.")])
    photo_count=select(func.count()).select_from(Photo).where(
        ((Photo.owner_type=="pet")&(Photo.owner_id==Pet.id))|((Photo.owner_type=="lost_case")&Photo.owner_id.in_(select(LostCase.id).where(LostCase.pet_id==Pet.id)))).correlate(Pet).scalar_subquery()
    for threshold in (1,3,5):
        metrics.append(metric(f"Mascotas con {threshold}+ fotos",count(db,Pet,*period_filters(Pet.created_at,from_at,to_at),photo_count>=threshold),"Fotos actualmente asociadas a la mascota y a sus avisos. Incluye datos previos; se diferencia de los nuevos hitos del funnel."))
    return metrics,{}


def matching(db,filters,from_at,to_at,job_provider,job_model,job_revision,job_source):
    summary=counters(db,filters);total=summary["total"]
    shown=count(db,Match,*filters,Match.first_shown_at.is_not(None));viewed=count(db,Match,*filters,Match.first_viewed_at.is_not(None))
    metrics=[metric(label,value,help,unit) for label,value,help,unit in (
        ("Recomendaciones",total,"Parejas aviso/avistamiento únicas por primera recomendación. Recalcular no genera una nueva.",""),
        ("Mostradas",shown,"Tarjetas que entraron al menos parcialmente en una pantalla visible. No basta devolverlas desde la API.",""),
        ("Vistas",viewed,"Al menos 50% del componente visible durante un segundo continuo, con la pestaña visible.",""),
        ("Revisadas",summary["reviewed"],"Última respuesta registrada por el dueño: confirmada, falsa o dudosa.",""),
        ("Confirmadas",summary["positive"],"El dueño indicó que era su mascota; no necesariamente que ya la recuperó.",""),
        ("Falsas",summary["false"],"El dueño indicó que no era su mascota.",""),("Dudosas",summary["uncertain"],"El dueño todavía no pudo decidir.",""),
        ("Pendientes",summary["pending"],"Recomendaciones sin una respuesta registrada.",""),
        ("Tasa de revisión",summary["review_rate"],"Revisadas / recomendadas.","%"),
        ("Tasa de confirmación entre decididas",summary["positive_rate"],"Confirmadas / (confirmadas + falsas). Tiene sesgo de participación; no es accuracy general del modelo.","%"),
        ("Tasa de falsas entre decididas",percent(summary["false"],summary["decided"]),"Falsas / (confirmadas + falsas).", "%"),
        ("Tasa de pendientes",percent(summary["pending"],total),"Pendientes / recomendadas.","%"),
        ("Tasa de dudosas",percent(summary["uncertain"],total),"Dudosas / recomendadas.","%"),
        ("Porcentaje visto",percent(viewed,total),"Vistas / recomendadas. La historia anterior al tracking no tiene vistas reconstruidas.","%"))]
    ranked=count(db,Match,*filters,outcome=="positive",Match.first_viewed_rank.is_not(None))
    topk={str(k):{"count":count(db,Match,*filters,outcome=="positive",Match.first_viewed_rank<=k),
        "percent":percent(count(db,Match,*filters,outcome=="positive",Match.first_viewed_rank<=k),ranked)} for k in (1,3,5)}
    topk.update({"denominator":ranked,"unknown_rank":summary["positive"]-ranked,
                "outside_top5":count(db,Match,*filters,outcome=="positive",Match.first_viewed_rank>5)})
    recs=select(Match.lost_case_id.label("case_id"),func.count().label("recommendations"),func.min(Match.recommended_at).label("first_recommendation"),
        func.min(Match.first_viewed_at).label("first_view"),func.count(Match.first_viewed_at).label("viewed")).where(*filters).group_by(Match.lost_case_id).subquery()
    response=select(func.min(MatchFeedbackEvent.created_at)).join(Match,MatchFeedbackEvent.match_id==Match.id).where(
        Match.lost_case_id==LostCase.id,*filters).correlate(LostCase).scalar_subquery()
    case_filters=period_filters(LostCase.created_at,from_at,to_at)
    base=select(LostCase.id,LostCase.created_at,recs.c.recommendations,recs.c.first_recommendation,recs.c.first_view,recs.c.viewed,response,
        RecoveryOutcome.recovered_at).outerjoin(recs,recs.c.case_id==LostCase.id).outerjoin(RecoveryOutcome,RecoveryOutcome.lost_case_id==LostCase.id).where(*case_filters)
    case_total=count(db,LostCase,*case_filters)
    with_recommendations=db.scalar(select(func.count()).select_from(LostCase).join(recs,recs.c.case_id==LostCase.id).where(*case_filters)) or 0
    sample=list(db.execute(base.order_by(LostCase.created_at.desc(),LostCase.id).limit(SAMPLE_LIMIT)))
    durations=defaultdict(list);counts=[];seen=[];first_rec=[]
    for _,created,n,first,view,nseen,feedback,recovered in sample:
        counts.append(n or 0);seen.append(nseen or 0)
        for name,time in (("recommendation",first),("viewed",view),("feedback",feedback),("recovery",recovered)):
            if time is not None:durations[name].append((aware(time)-aware(created)).total_seconds())
        if first:first_rec.append(max(0,(aware(first)-aware(created)).total_seconds()))
    utility={"searches":case_total,"with_recommendation":with_recommendations,"without_recommendation":case_total-with_recommendations,
        "recommended_percent":percent(with_recommendations,case_total),"average_matches":sum(counts)/len(counts) if counts else None,
        "median_matches":median(counts) if counts else None,"average_viewed":sum(seen)/len(seen) if seen else None,
        "sample_n":len(sample),"sample_limit":SAMPLE_LIMIT,"sampled":case_total>SAMPLE_LIMIT,
        "first_recommendation_hours":{name:percent(sum(1 for value in first_rec if condition(value)),len(first_rec))
           for name,condition in (("under_1",lambda v:v<3600),("under_6",lambda v:v<21600),("under_24",lambda v:v<86400),("over_24",lambda v:v>=86400))},
        "first_recommendation_denominator":len(first_rec),"timings":{name:distribution(durations[name]) for name in ("recommendation","viewed","feedback","recovery")}}
    job_time_filters=period_filters(AnalysisJob.created_at,from_at,to_at)
    job_filters=list(job_time_filters)
    if job_provider!="all":job_filters.append(AnalysisJob.provider==job_provider)
    if job_model:job_filters.append(AnalysisJob.model==job_model)
    revision_col=func.coalesce(AnalysisJob.input_snapshot["spec"]["revision"].as_string(),AnalysisJob.metrics["model_revision"].as_string())
    if job_revision:job_filters.append(revision_col==job_revision)
    if job_source!="all":job_filters.append(AnalysisJob.source_type==job_source)
    job_counts={key:0 for key in ("PENDING","DISPATCHING","QUEUED","RUNNING","SUCCEEDED","FAILED","STALE","SKIPPED")}
    job_counts.update(dict(db.execute(select(AnalysisJob.status,func.count()).where(*job_filters).group_by(AnalysisJob.status)).all()))
    jobs=list(db.execute(select(AnalysisJob.created_at,AnalysisJob.started_at,AnalysisJob.finished_at,AnalysisJob.metrics,AnalysisJob.attempts)
        .where(*job_filters).order_by(AnalysisJob.created_at.desc(),AnalysisJob.id).limit(SAMPLE_LIMIT)))
    performance=defaultdict(list);retries=cold=cold_measured=0
    for created,started,finished,details,attempts in jobs:
        if started:performance["queue_wait"].append((aware(started)-aware(created)).total_seconds())
        if finished and started:performance["processing"].append((aware(finished)-aware(started)).total_seconds())
        if finished:performance["end_to_end"].append((aware(finished)-aware(created)).total_seconds())
        for field in ("model_load_ms","total_ms","cpu_ms","ollama_request_ms","visual_inference_ms"):
            if isinstance((details or {}).get(field),(int,float)):performance[field].append(details[field]/1000)
        retries+=int(attempts>1);cold+=int(bool((details or {}).get("cold_start")))
        cold_measured+=int("cold_start" in (details or {}))
    segments=[{"provider":p,"model":m,"revision":r or "unknown","source":s,"prompt_version":prompt,"preprocessing_version":pre,"jobs":n}
        for p,m,r,s,prompt,pre,n in db.execute(select(AnalysisJob.provider,AnalysisJob.model,revision_col,
            AnalysisJob.source_type,AnalysisJob.prompt_version,AnalysisJob.preprocessing_version,func.count()).where(*job_filters)
            .group_by(AnalysisJob.provider,AnalysisJob.model,revision_col,AnalysisJob.source_type,
                      AnalysisJob.prompt_version,AnalysisJob.preprocessing_version).order_by(func.count().desc()).limit(100))]
    job_total=sum(job_counts.values())
    dimensions=job_filters[len(job_time_filters):]
    throughput_filters=[*dimensions,AnalysisJob.status=="SUCCEEDED",AnalysisJob.finished_at.is_not(None),
                        *period_filters(AnalysisJob.finished_at,from_at,to_at)]
    completed=count(db,AnalysisJob,*throughput_filters)
    throughput_start=from_at or db.scalar(select(func.min(AnalysisJob.finished_at)).where(*throughput_filters))
    hours=max((aware(to_at or utcnow())-aware(throughput_start)).total_seconds()/3600,1/3600) if throughput_start else None
    operations={"statuses":job_counts,"total":job_total,"sample_n":len(jobs),"sampled":job_total>SAMPLE_LIMIT,
        "retry_rate":percent(retries,len(jobs)),"cold_start_rate":percent(cold,cold_measured),"cold_start_n":cold_measured,"failure_rate":percent(job_counts.get("FAILED",0),job_total),
        "timings":{key:distribution(value) for key,value in performance.items()},"segments":segments,
        "completed_per_hour":round(completed/hours,3) if hours else None,"throughput_completed":completed,
        "resources_note":"CPU/RAM: métricas del proceso en /internal/metrics y docker stats. Colas, workers, throughput y latencias: Prometheus existente. Sin historiales de recursos duplicados en la base."}
    # Reuse the same JSON expressions/bind parameters: PostgreSQL must see identical
    # expressions in SELECT and GROUP BY, even when JSON keys are bound parameters.
    version_columns=(Match.recommendation_snapshot["visual_provider"].as_string(),
        Match.recommendation_snapshot["actual_visual_space"]["model"].as_string(),
        Match.recommendation_snapshot["actual_visual_space"]["revision"].as_string())
    versions=[{"provider":p or "unknown","model":m or "unknown","revision":r or "unknown","recommendations":n}
        for p,m,r,n in db.execute(select(*version_columns,func.count()).where(*filters).group_by(*version_columns).limit(100))]
    return metrics,{"topk":topk,"utility":utility,"operations":operations,"versions":versions}


def community(db,from_at,to_at):
    filters=period_filters(Observation.created_at,from_at,to_at)
    photo=exists(select(Photo.id).where(Photo.owner_type=="observation",Photo.owner_id==Observation.id))
    rec=exists(select(Match.id).where(Match.observation_id==Observation.id,Match.recommended_at.is_not(None)))
    confirmed=exists(select(Match.id).where(Match.observation_id==Observation.id,outcome=="positive"))
    recovery=exists(select(RecoveryOutcome.lost_case_id).where(RecoveryOutcome.observation_id==Observation.id,
                            RecoveryOutcome.reason.in_(["MASCOMATCH_MATCH","MASCOMATCH_SIGHTING"])))
    return [metric(label,count(db,Observation,*filters,*extra),"Reportes existentes creados en el período. Fotos, cuenta vinculada y resultado actuales; la serie conserva los eventos nuevos aunque luego se eliminen registros.")
        for label,extra in (("Avistamientos y encontrados",[]),("Sin cuenta",[Observation.author_id.is_(None)]),
            ("Con cuenta",[Observation.author_id.is_not(None)]),("Con foto",[photo]),("Sin foto",[~photo]),
            ("Vinculados a un aviso",[Observation.linked_case_id.is_not(None)]),("Generales",[Observation.linked_case_id.is_(None)]),
            ("Con recomendación",[rec]),("Con coincidencia confirmada",[confirmed]),("Con recuperación atribuida",[recovery]))]


def csv_cell(value):
    text="" if value is None else str(value)
    return "'"+text if text.lstrip().startswith(("=","+","-","@","\t","\r","\n")) else text


def aggregate_csv(data):
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(["tipo","fecha","metrica","valor","pais","departamento","localidad"])
    for item in data["metrics"]:writer.writerow(["resumen","",csv_cell(item["label"]),csv_cell(item["value"]),"","",""])
    for point in data["series"]:writer.writerow(["serie",point["date"],csv_cell(point["name"]),point["value"],"","",""])
    for item in data.get("geography",[]):writer.writerow(["zona","",csv_cell(item["page"]+":"+item["event"]),item["count"],csv_cell(item["country"]),csv_cell(item["department"]),csv_cell(item["locality"])])
    return "\ufeff"+stream.getvalue()


@router.get("/{section}")
def dashboard(section:Literal["growth","usage","matching","impact","inventory"],response:Response,
    days:int=Query(default=30,ge=0,le=3650),from_at:AwareDatetime | None=None,to_at:AwareDatetime | None=None,
    group:Literal["day","week","month"]="day",source:Literal["all","GENERAL","LINKED"]="all",
    provider:Literal["all","pet_reid","open_clip","NONE"]="all",model:str | None=Query(default=None,max_length=120),
    revision:str | None=Query(default=None,max_length=80),job_source:Literal["all","text","image","embedding"]="all",
    job_provider:Literal["all","ollama","pet_reid","open_clip"]="all",job_model:str | None=Query(default=None,max_length=120),
    job_revision:str | None=Query(default=None,max_length=80),export_csv:bool=False,
    country:str | None=Query(default=None,pattern="^[A-Z]{2}$"),department:str | None=Query(default=None,max_length=80),
    locality:str | None=Query(default=None,max_length=80),db=Depends(get_db),user=Depends(administrator)):
    response.headers["Cache-Control"]="no-store"
    fingerprint=hashlib.sha256(json.dumps([days,str(from_at),str(to_at),group,source,provider,model,revision,
        job_source,job_provider,job_model,job_revision,country,department,locality,settings.analytics_enabled,
        settings.analytics_raw_days,settings.analytics_daily_days],separators=(",",":")).encode()).hexdigest()
    cached=cached_dashboard(section,fingerprint)
    if cached is not None:
        if export_csv:return Response(aggregate_csv(cached),media_type="text/csv; charset=utf-8",headers={"Cache-Control":"no-store",
            "Content-Disposition":f'attachment; filename="mascomatch-{section}-aggregate.csv"',"X-Content-Type-Options":"nosniff"})
        return cached
    if from_at is None and to_at is None and days:from_at=utcnow()-timedelta(days=days)
    period_filters(LostCase.created_at,from_at,to_at)
    tracking=db.get(AnalyticsTracking,1)
    if section in {"matching","impact"}:
        model_events,event_filters,amount,facts,series,precision=ProductDaily,[],func.sum(ProductDaily.count),{},[],"event"
    else:
        model_events,event_filters,amount,facts,series,precision=product(db,from_at,to_at,group,
            ["lost_case_created","sighting_created"] if section=="usage" else None)
    geo_filters=[*([model_events.country==country] if country else []),*([model_events.department==department] if department else []),
                 *([model_events.locality==locality] if locality else [])]
    if section=="inventory" and geo_filters:
        event_filters=[*event_filters,*geo_filters]
        date=bucket(db,model_events.created_at if model_events is ProductEvent else model_events.day,group,date_only=model_events is ProductDaily)
        series=[{"date":day,"name":name,"value":value} for day,name,value in db.execute(select(date,model_events.name,amount).where(*event_filters)
            .group_by(date,model_events.name).order_by(date))]
    extra={};metrics=[]
    if section=="growth":metrics,extra=growth(db,facts)
    if section=="usage":
        metrics,extra=usage(db,from_at,to_at)
        extra["community"]=community(db,from_at,to_at)
    if section=="matching":
        filters=scope(0,source,"all",from_at,to_at,provider,model,revision)
        metrics,extra=matching(db,filters,from_at,to_at,job_provider,job_model,job_revision,job_source)
        rec_bucket=bucket(db,Match.recommended_at,group)
        series=[{"date":day,"name":"recommendation_generated","value":n} for day,n in db.execute(
            select(rec_bucket,func.count()).where(*filters).group_by(rec_bucket).order_by(rec_bucket))]
        viewed_bucket=rec_bucket  # Cohort by recommendation date; actual view-day inventory is separate.
        series.extend({"date":day,"name":"match_viewed","value":n} for day,n in db.execute(
            select(viewed_bucket,func.count()).where(*filters,Match.first_viewed_at.is_not(None)).group_by(viewed_bucket).order_by(viewed_bucket)))
    if section=="impact":
        recoveries=dict(db.execute(select(RecoveryOutcome.reason,func.count()).where(*period_filters(RecoveryOutcome.recovered_at,from_at,to_at)).group_by(RecoveryOutcome.reason)).all())
        total=sum(recoveries.values());assisted=sum(recoveries.get(name,0) for name in ("MASCOMATCH_MATCH","MASCOMATCH_SIGHTING"))
        legacy=count(db,LostCase,LostCase.status=="FOUND",~exists(select(RecoveryOutcome.lost_case_id).where(RecoveryOutcome.lost_case_id==LostCase.id)))
        metrics=[metric(label,value,help) for label,value,help in (
            ("Recuperaciones registradas",total,"Outcomes únicos por búsqueda, filtrados por fecha real de marcado desde que comenzó este seguimiento."),
            ("El dueño indicó ayuda de MascoMatch",assisted,"Atribución declarada por el dueño, no prueba de causalidad."),
            ("A través de una coincidencia",recoveries.get("MASCOMATCH_MATCH",0),"El dueño eligió la opción de coincidencia de MascoMatch."),
            ("A través de un avistamiento",recoveries.get("MASCOMATCH_SIGHTING",0),"El dueño eligió la opción de avistamiento recibido por MascoMatch."),
            ("Otra vía",total-assisted-recoveries.get("PREFER_NOT_TO_SAY",0),"Redes, WhatsApp, carteles, instituciones, regreso por sí sola u otra forma."),
            ("Prefirió no responder",recoveries.get("PREFER_NOT_TO_SAY",0),"La persona pudo cerrar la búsqueda sin atribuir el reencuentro."),
            ("Recuperadas históricas sin atribución",legacy,"Estado FOUND previo sin outcome. Total histórico, sin fecha de recuperación inventada; no se filtra por fecha de recuperación."))]
        recovery_times=list(db.execute(select(LostCase.created_at,RecoveryOutcome.recovered_at).join(RecoveryOutcome,RecoveryOutcome.lost_case_id==LostCase.id)
            .where(*period_filters(RecoveryOutcome.recovered_at,from_at,to_at)).order_by(RecoveryOutcome.recovered_at.desc()).limit(SAMPLE_LIMIT)))
        extra={"reasons":recoveries,"community":community(db,from_at,to_at),"impact_timings":{"recovery":distribution(
            [(aware(end)-aware(start)).total_seconds() for start,end in recovery_times])},"timing_sampled":total>SAMPLE_LIMIT}
        recovery_bucket=bucket(db,RecoveryOutcome.recovered_at,group)
        series=[{"date":day,"name":"recovery","value":n} for day,n in db.execute(select(recovery_bucket,func.count())
            .where(*period_filters(RecoveryOutcome.recovered_at,from_at,to_at)).group_by(recovery_bucket).order_by(recovery_bucket))]
    if section=="inventory":
        surfaces=[]
        definitions=[("Inicio","HOME","page_view"),("Avisos de pérdida","LOST_CASE","page_view"),
                     ("Coincidencias efectivamente vistas","MATCHES","match_viewed"),("Experiencia de recuperación","RECOVERY","page_view")]
        for label,page,name in definitions:
            filters=[*event_filters,model_events.page==page,model_events.name==name]
            total=db.scalar(select(amount).select_from(model_events).where(*filters)) or 0
            metrics.append(metric(label,total,"Uso real potencial para evaluar oportunidades futuras. No son impresiones publicitarias vendidas ni garantizadas."))
            session_col=model_events.session_id if model_events is ProductEvent else model_events.session_key
            sessions=db.scalar(select(func.count(func.distinct(func.nullif(session_col,"unknown"))) if model_events is ProductDaily else func.count(func.distinct(session_col))).where(*filters)) or 0
            visitors=db.scalar(select(func.count(func.distinct(func.nullif(model_events.visitor_id,"unknown")))).where(*filters)) or 0
            surfaces.append({"surface":label,"events":total,"sessions":sessions,"visitors":visitors})
        geo=[{"country":country,"department":department,"locality":locality,"page":page,"event":name,"count":n}
            for country,department,locality,page,name,n in db.execute(select(model_events.country,model_events.department,model_events.locality,
                model_events.page,model_events.name,amount).where(*event_filters,model_events.page.in_(["HOME","LOST_CASE","MATCHES","RECOVERY"]),
                    model_events.name.in_(["page_view","match_viewed","recovery"]))
                .group_by(model_events.country,model_events.department,model_events.locality,model_events.page,model_events.name)
                .order_by(amount.desc()).limit(200))]
        case_views=[{"public_id":public_id,"views":views} for public_id,views in db.execute(
            select(LostCase.public_number,amount).join(model_events,model_events.case_id==LostCase.id)
            .where(*event_filters,model_events.name=="match_viewed").group_by(LostCase.public_number).order_by(amount.desc()).limit(100))]
        for item in case_views:item["public_id"]=f"MM-{item['public_id']:06d}"
        active_geo=[LostCase.status=="ACTIVE",*period_filters(LostCase.created_at,from_at,to_at)]
        cg=LostCase.analytics_geo["country"].as_string();dg=LostCase.analytics_geo["department"].as_string();lg=LostCase.analytics_geo["locality"].as_string()
        for column,value in ((cg,country),(dg,department),(lg,locality)):
            if value:active_geo.append(column==value)
        active=[{"country":c or "ZZ","department":d or "unknown","locality":l or "unknown","active":n}
            for c,d,l,n in db.execute(select(cg,dg,lg,func.count()).where(*active_geo).group_by(cg,dg,lg).order_by(func.count().desc()).limit(200))]
        extra={"surfaces":surfaces,"case_views":case_views,"active_searches":active,"geography":geo,
            "geo_note":"Zona contextual, nunca ubicación por IP. Las páginas sin zona quedan desconocidas. Hasta 200 agrupaciones y 100 avisos por consulta; el filtro permite consultar cada zona."}
    data={"section":section,"metrics":metrics,"series":series,"facts":facts,"analytics_started_at":tracking.started_at if tracking else None,
        "analytics_enabled":settings.analytics_enabled,
        "cache_max_age_seconds":CACHE_SECONDS if settings.app_env=="production" else 0,
        "pending_rollups":count(db,ProductEvent,ProductEvent.aggregated.is_(False)),
        "generated_at":utcnow(),"time_precision":precision,"retention":{"raw_days":settings.analytics_raw_days,"daily_days":settings.analytics_daily_days},
        "history_note":"Las visitas, vistas y ranks empiezan en la fecha indicada. Los registros operativos anteriores se identifican como historia existente. Las series nuevas no reconstruyen visitas pasadas.",**extra}
    cached_dashboard(section,fingerprint,data)
    if export_csv:return Response(aggregate_csv(data),media_type="text/csv; charset=utf-8",headers={"Cache-Control":"no-store",
        "Content-Disposition":f'attachment; filename="mascomatch-{section}-aggregate.csv"',"X-Content-Type-Options":"nosniff"})
    return data
