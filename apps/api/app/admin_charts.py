"""Aggregated chart data over preserved records; no personal data or invented trends."""
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func, literal, select, union_all
from app.admin_period import period_filters
from app.analysis.service import utcnow
from app.models import EmailDeliveryLog, LostCase, Observation, User

ZONE = ZoneInfo("America/Montevideo")


def chart_data(db, from_at, to_at, job_states, mail_states, user_scope):
    events = union_all(
        select(User.created_at.label("at"), literal("users").label("kind")),
        select(LostCase.created_at, literal("publications")),
        select(Observation.created_at, literal("publications")),
    ).subquery()
    filters = period_filters(events.c.at, from_at, to_at)
    first = db.scalar(select(func.min(events.c.at)).where(*filters))
    timeline, unit = [], "day"
    if first is not None:
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        # Trim leading years with no preserved records; never manufacture past activity.
        start = max(first, from_at) if from_at else first
        end = min(to_at or utcnow(), utcnow())
        days = (end - start).days
        unit = "day" if days <= 45 else "week" if days <= 365 else "month" if days <= 3650 else "year"
        bucket = func.date_trunc(unit, func.timezone("America/Montevideo", events.c.at))
        rows = db.execute(select(bucket.label("bucket"), events.c.kind, func.count())
            .where(*filters).group_by(bucket, events.c.kind).order_by(bucket)).all()
        counts = {}
        for at, kind, total in rows:
            counts.setdefault(at.date(), {"users": 0, "publications": 0})[kind] = total
        cursor = start.astimezone(ZONE).date()
        if unit == "week": cursor -= timedelta(days=cursor.weekday())
        elif unit == "month": cursor = cursor.replace(day=1)
        elif unit == "year": cursor = cursor.replace(month=1, day=1)
        last = end.astimezone(ZONE).date()
        # Exclusive end at local midnight must not add a bucket outside the filter.
        if to_at and end == to_at and end.astimezone(ZONE).time().isoformat() == "00:00:00":
            last -= timedelta(days=1)
        while cursor <= last:
            timeline.append({"date": cursor.isoformat(), **counts.get(cursor, {"users": 0, "publications": 0})})
            if unit == "day": cursor += timedelta(days=1)
            elif unit == "week": cursor += timedelta(days=7)
            elif unit == "month": cursor = cursor.replace(year=cursor.year + (cursor.month == 12), month=cursor.month % 12 + 1)
            else: cursor = cursor.replace(year=cursor.year + 1)
    jobs = [
        {"label": "Completados", "value": job_states.get("SUCCEEDED", 0), "tone": "teal"},
        {"label": "En espera", "value": sum(job_states.get(s, 0) for s in ("PENDING", "DISPATCHING", "QUEUED")), "tone": "blue"},
        {"label": "En proceso", "value": job_states.get("RUNNING", 0), "tone": "violet"},
        {"label": "Fallidos", "value": job_states.get("FAILED", 0), "tone": "coral"},
        {"label": "Reemplazados", "value": job_states.get("STALE", 0), "tone": "muted"},
    ]
    publication_types = []
    for label, model, condition, tone in (
        ("Avisos de pérdida", LostCase, literal(True), "coral"),
        ("Avistamientos", Observation, Observation.source_type == "USER_SIGHTING", "blue"),
        ("Reportes de mascotas encontradas", Observation, Observation.source_type == "FOUND_ANIMAL", "teal"),
    ):
        total = db.scalar(select(func.count()).select_from(model)
            .where(condition, *period_filters(model.created_at, from_at, to_at))) or 0
        publication_types.append({"label": label, "value": total, "tone": tone})
    accounts = dict(db.execute(select(User.status, func.count()).where(*user_scope).group_by(User.status)).all())
    account_total = sum(accounts.values())
    verified = db.scalar(select(func.count()).select_from(User).where(*user_scope, User.email_verified_at.is_not(None))) or 0
    mail_kinds = [{"label": label, "value": value, "tone": "blue"} for label, value in db.execute(
        select(EmailDeliveryLog.kind, func.count()).where(EmailDeliveryLog.status == "SENT",
            *period_filters(EmailDeliveryLog.created_at, from_at, to_at)).group_by(EmailDeliveryLog.kind).order_by(EmailDeliveryLog.kind))]
    return {"timeline": timeline, "timeline_unit": unit, "jobs": jobs, "publications": publication_types,
        "accounts": {"total": account_total, "enabled": accounts.get("ACTIVE", 0), "blocked": accounts.get("BLOCKED", 0), "verified": verified},
        "mail_kinds": mail_kinds, "mail_status": mail_states}
