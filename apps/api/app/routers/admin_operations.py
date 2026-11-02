"""Bounded, private operational views. Never serialize tokens, secrets or AI inputs."""
from typing import Literal
from datetime import timedelta
from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime
from sqlalchemy import and_, func, literal, or_, select, union_all
from app.admin_access import administrator
from app.admin_period import period_filters
from app.admin_charts import chart_data
from app.ops.backup_status import read_status
from app.analysis.service import utcnow
from app.species import owner_is_supported
from app.db.session import get_db
from app.models import (AccountToken, AdminAudit, AnalysisJob, ContactMessage, EmailDeliveryLog,
    LostCase, Notification, Observation, OperationalTracking, Pet, PhotoReminder, User, UserActivity)

router = APIRouter(prefix="/admin/operations", tags=["admin-operations"])
SECTION = Literal["users", "jobs", "mail", "mail_queue", "contacts", "publications", "audit"]
STATE = Literal["all", "ACTIVE", "BLOCKED", "verified", "unverified", "recent", "waiting", "PENDING", "DISPATCHING",
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "STALE", "SENT", "PREVIEWED", "VISIBLE", "HIDDEN"]
DATE_FIELD = Literal["created", "activity", "finished"]


def count(db, model, filters=()):
    return db.scalar(select(func.count()).select_from(model).where(*filters)) or 0


def states(db, model, column, filters):
    return dict(db.execute(select(column, func.count()).select_from(model).where(*filters).group_by(column)).all())


def mail_requests():
    # Source rows are requests; several notifications may become a single email.
    parts = []
    for model, source, kind, state, identity, attempts, available, user_id in (
        (Notification, "notification", literal("ALERT"), Notification.email_status, Notification.id, Notification.email_attempts, Notification.email_available_at, Notification.owner_id),
        (AccountToken, "account_token", AccountToken.kind, AccountToken.email_status, AccountToken.id, AccountToken.email_attempts, AccountToken.email_available_at, AccountToken.user_id),
        (PhotoReminder, "photo_reminder", literal("PHOTO_REMINDER"), PhotoReminder.status, PhotoReminder.lost_case_id, PhotoReminder.attempts, PhotoReminder.available_at, literal(None)),
        (ContactMessage, "contact", literal("CONTACT_FORWARD"), ContactMessage.email_status, ContactMessage.id, ContactMessage.email_attempts, ContactMessage.email_available_at, literal(None)),
    ):
        filters = [state.in_(["PENDING", "FAILED"])]
        if model is Notification:
            filters += [Notification.is_active.is_(True), Notification.read_at.is_(None), Notification.archived_at.is_(None)]
        if model is AccountToken:
            filters += [AccountToken.consumed_at.is_(None), AccountToken.expires_at > utcnow()]
        parts.append(select(identity.label("id"), literal(source).label("source_type"), kind.label("kind"),
            state.label("status"), attempts.label("attempts"), available.label("available_at"),
            model.created_at.label("created_at"), user_id.label("user_id")).where(*filters))
    return union_all(*parts).subquery()


def publications():
    lost = select(LostCase.id.label("id"), literal("lost_case").label("kind"), LostCase.public_number,
        Pet.name.label("title"), Pet.species, LostCase.description, LostCase.status.label("case_status"),
        LostCase.moderation_status.label("visibility"), User.name.label("author_name"), User.id.label("author_id"),
        User.status.label("author_status"), LostCase.public_location, LostCase.created_at)
    lost = lost.join(Pet, Pet.id == LostCase.pet_id).join(User, User.id == Pet.owner_id)
    observation = select(Observation.id, literal("observation"), Observation.public_number,
        Observation.source_type, Observation.species, Observation.description, literal(None),
        Observation.moderation_status, User.name, User.id, User.status, Observation.public_location, Observation.created_at)
    observation = observation.outerjoin(User, User.id == Observation.author_id)
    return union_all(lost, observation).subquery()


@router.get("")
def overview(response: Response, from_at: AwareDatetime | None = None, to_at: AwareDatetime | None = None,
             db=Depends(get_db), user=Depends(administrator)):
    response.headers["Cache-Control"] = "no-store"
    user_scope = period_filters(User.created_at, from_at, to_at)
    case_scope = period_filters(LostCase.created_at, from_at, to_at)
    job_scope = period_filters(AnalysisJob.created_at, from_at, to_at)
    mail_scope = period_filters(EmailDeliveryLog.created_at, from_at, to_at)
    contact_scope = period_filters(ContactMessage.created_at, from_at, to_at)
    activity_scope = period_filters(UserActivity.occurred_at, from_at, to_at)
    active = db.scalar(select(func.count(func.distinct(UserActivity.user_id))).where(*activity_scope)) or 0
    queue = mail_requests()
    queued = db.scalar(select(func.count()).select_from(queue).where(queue.c.status == "PENDING")) or 0
    failed = db.scalar(select(func.count()).select_from(queue).where(queue.c.status == "FAILED")) or 0
    job_states = states(db, AnalysisJob, AnalysisJob.status, job_scope)
    mail_states = states(db, EmailDeliveryLog, EmailDeliveryLog.status, mail_scope)
    tracking = db.get(OperationalTracking, 1)
    return {"metrics": [
        {"label": "Cuentas registradas", "value": count(db, User, user_scope), "help": "Registradas en el período seleccionado."},
        {"label": "Mascotas recuperadas", "value": count(db, LostCase, [*case_scope, LostCase.status == "FOUND"]), "help": "Avisos creados en el período y marcados como recuperados."},
        {"label": "Usuarios con actividad", "value": active, "help": "Cuentas distintas con una sesión usada en el período."},
        {"label": "Actividad en los últimos 15 min", "value": count(db, User, [User.status == "ACTIVE", User.last_active_at >= utcnow() - timedelta(minutes=15)]), "help": "Estado actual de toda la plataforma; incluye consultas automáticas del sitio."},
        {"label": "Cuentas bloqueadas", "value": count(db, User, [*user_scope, User.status == "BLOCKED"]), "help": "Entre las cuentas registradas en el período."},
        {"label": "Trabajos en espera", "value": sum(job_states.get(s, 0) for s in ("PENDING", "DISPATCHING", "QUEUED")), "help": "Estado actual de trabajos creados en el período."},
        {"label": "Trabajos en proceso", "value": job_states.get("RUNNING", 0), "help": "Creados en el período y actualmente en ejecución."},
        {"label": "Trabajos completados", "value": job_states.get("SUCCEEDED", 0), "help": "Finalizados correctamente, creados en el período."},
        {"label": "Trabajos fallidos", "value": job_states.get("FAILED", 0), "help": "Agotaron sus reintentos; creados en el período."},
        {"label": "Correos enviados", "value": mail_states.get("SENT", 0), "help": "Mensajes aceptados por SMTP en el período."},
        {"label": "Intentos de correo fallidos", "value": mail_states.get("FAILED", 0), "help": "Incluye intentos que luego pudieron enviarse."},
        {"label": "Contactos recibidos", "value": count(db, ContactMessage, contact_scope), "help": "Mensajes conservados, recibidos en el período."}],
        "mail_queue": {"pending": queued, "failed": failed},
        "backups": read_status(),
        "charts": chart_data(db, from_at, to_at, job_states, mail_states, user_scope),
        "tracking_started_at": tracking.started_at if tracking else None, "generated_at": utcnow()}


@router.get("/{section}")
def records(section: SECTION, response: Response, from_at: AwareDatetime | None = None, to_at: AwareDatetime | None = None,
            state: STATE = "all", date_field: DATE_FIELD = "created", q: str = Query(default="", max_length=120),
            kind: Literal["all", "lost_case", "observation"] = "all", limit: int = Query(default=25, ge=1, le=100),
            offset: int = Query(default=0, ge=0, le=100000), db=Depends(get_db), user=Depends(administrator)):
    response.headers["Cache-Control"] = "no-store"
    term = q.strip()
    pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    items, summary = [], {}
    if section == "users":
        column = User.last_active_at if date_field == "activity" else User.created_at
        filters = period_filters(column, from_at, to_at)
        if date_field == "activity":
            # Any activity inside the range, even if the user was also active after it.
            filters = [select(UserActivity.user_id).where(UserActivity.user_id == User.id,
                *period_filters(UserActivity.occurred_at, from_at, to_at)).exists()]
        if term:
            filters.append(or_(User.name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\")))
        summary = states(db, User, User.status, filters)
        summary["verified"] = count(db, User, [*filters, User.email_verified_at.is_not(None)])
        summary["unverified"] = count(db, User, [*filters, User.email_verified_at.is_(None)])
        recent = [User.status == "ACTIVE", User.last_active_at >= utcnow() - timedelta(minutes=15)]
        summary["recent"] = count(db, User, [*filters, *recent])
        if state in ("ACTIVE", "BLOCKED"):
            filters.append(User.status == state)
        elif state in ("verified", "unverified"):
            filters.append(User.email_verified_at.is_not(None) if state == "verified" else User.email_verified_at.is_(None))
        elif state == "recent":
            filters.extend(recent)
        query = select(User).where(*filters)
        total = count(db, User, filters)
        order = column.desc().nulls_last()
        cases = select(func.count()).select_from(LostCase).join(Pet).where(Pet.owner_id == User.id).correlate(User).scalar_subquery()
        sightings = select(func.count()).select_from(Observation).where(Observation.author_id == User.id).correlate(User).scalar_subquery()
        for account, case_count, obs_count in db.execute(query.add_columns(cases, sightings).order_by(order, User.id).offset(offset).limit(limit)):
            items.append({"id": account.id, "name": account.name, "email": account.email, "phone": account.phone,
                "status": account.status, "verified": account.email_verified, "created_at": account.created_at,
                "last_active_at": account.last_active_at, "lost_cases": case_count, "observations": obs_count,
                "is_self": account.id == user.id})
    elif section == "jobs":
        column = AnalysisJob.finished_at if date_field == "finished" else AnalysisJob.created_at
        filters = period_filters(column, from_at, to_at)
        if date_field == "finished":
            filters.append(AnalysisJob.finished_at.is_not(None))
        if term:
            filters.append(or_(AnalysisJob.model.ilike(pattern, escape="\\"), AnalysisJob.error_code.ilike(pattern, escape="\\")))
        summary = states(db, AnalysisJob, AnalysisJob.status, filters)
        summary["waiting"] = sum(summary.get(s, 0) for s in ("PENDING", "DISPATCHING", "QUEUED"))
        if state == "waiting":
            filters.append(AnalysisJob.status.in_(["PENDING", "DISPATCHING", "QUEUED"]))
        elif state != "all":
            filters.append(AnalysisJob.status == state)
        total = count(db, AnalysisJob, filters)
        fields = ("id", "owner_type", "owner_id", "source_type", "provider", "model", "status", "attempts",
            "max_attempts", "created_at", "available_at", "started_at", "finished_at", "error_code")
        for job in db.scalars(select(AnalysisJob).where(*filters).order_by(column.desc(), AnalysisJob.id).offset(offset).limit(limit)):
            items.append({field: getattr(job, field) for field in fields})
    elif section == "mail":
        filters = period_filters(EmailDeliveryLog.created_at, from_at, to_at)
        if term:
            filters.append(EmailDeliveryLog.kind.ilike(pattern, escape="\\"))
        summary = states(db, EmailDeliveryLog, EmailDeliveryLog.status, filters)
        if state != "all":
            filters.append(EmailDeliveryLog.status == state)
        total = count(db, EmailDeliveryLog, filters)
        query = select(EmailDeliveryLog, User.name).outerjoin(User, User.id == EmailDeliveryLog.recipient_user_id)
        for entry, name in db.execute(query.where(*filters).order_by(EmailDeliveryLog.created_at.desc(), EmailDeliveryLog.id).offset(offset).limit(limit)):
            items.append({"id": entry.id, "kind": entry.kind, "status": entry.status, "created_at": entry.created_at,
                "item_count": entry.item_count, "recipient_name": name, "source_type": entry.source_type,
                "source_ids": entry.source_ids})
    elif section == "mail_queue":
        queue = mail_requests()
        filters = period_filters(queue.c.created_at, from_at, to_at)
        if term:
            filters.append(queue.c.kind.ilike(pattern, escape="\\"))
        summary = states(db, queue, queue.c.status, filters)
        if state != "all":
            filters.append(queue.c.status == state)
        total = count(db, queue, filters)
        items = [dict(row._mapping) for row in db.execute(select(queue).where(*filters)
            .order_by(queue.c.created_at.desc(), queue.c.source_type, queue.c.id).offset(offset).limit(limit))]
    elif section == "contacts":
        filters = period_filters(ContactMessage.created_at, from_at, to_at)
        if term:
            filters.append(or_(ContactMessage.name.ilike(pattern, escape="\\"), ContactMessage.email.ilike(pattern, escape="\\"),
                ContactMessage.message.ilike(pattern, escape="\\")))
        summary = states(db, ContactMessage, ContactMessage.email_status, filters)
        if state != "all":
            filters.append(ContactMessage.email_status == state)
        total = count(db, ContactMessage, filters)
        fields = ("id", "name", "email", "topic", "message", "created_at", "email_status", "email_sent_at", "email_attempts")
        items = [{field: getattr(entry, field) for field in fields} for entry in db.scalars(select(ContactMessage)
            .where(*filters).order_by(ContactMessage.created_at.desc(), ContactMessage.id).offset(offset).limit(limit))]
    elif section == "publications":
        entries = publications()
        filters = period_filters(entries.c.created_at, from_at, to_at)
        if kind != "all":
            filters.append(entries.c.kind == kind)
        if term:
            search = [entries.c.title.ilike(pattern, escape="\\"), entries.c.description.ilike(pattern, escape="\\"),
                entries.c.author_name.ilike(pattern, escape="\\")]
            digits = term.upper().removeprefix("MM-")
            if digits.isdigit() and len(digits) <= 15:
                search.append(entries.c.public_number == int(digits))
            filters.append(or_(*search))
        summary = states(db, entries, entries.c.visibility, filters)
        if state != "all":
            filters.append(entries.c.visibility == state)
        total = count(db, entries, filters)
        for row in db.execute(select(entries).where(*filters).order_by(entries.c.created_at.desc(), entries.c.id).offset(offset).limit(limit)):
            item = dict(row._mapping)
            item["public_id"] = f"MM-{item.pop('public_number'):06d}"
            item["in_scope"] = owner_is_supported(db,item["kind"],item["id"])
            items.append(item)
    else:
        filters = period_filters(AdminAudit.created_at, from_at, to_at)
        if term:
            filters.append(AdminAudit.action.ilike(pattern, escape="\\"))
        total = count(db, AdminAudit, filters)
        items = [{"id": entry.id, "action": entry.action, "target_type": entry.target_type, "target_id": entry.target_id,
            "created_at": entry.created_at, "reason": entry.details.get("reason", "")}
            for entry in db.scalars(select(AdminAudit).where(*filters)
                .order_by(AdminAudit.created_at.desc(), AdminAudit.id).offset(offset).limit(limit))]
    tracking = db.get(OperationalTracking, 1)
    return {"items": items, "summary": summary, "total": total, "limit": limit, "offset": offset,
        "tracking_started_at": tracking.started_at if tracking else None, "generated_at": utcnow()}
