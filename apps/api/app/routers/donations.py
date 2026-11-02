from datetime import timedelta
import hmac
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.admin_access import administrator
from app.admin_period import period_filters
from app.analysis.service import utcnow
from app.core.config import settings
from app.db.session import get_db
from app.matching.linked import aware
from app.models import Donation, DonationSync
from app.payments import MAX_AMOUNT, MercadoPago, PaymentError, browser_digest, checked_checkout, enqueue, mode_matches, validate_order, validate_signature

router = APIRouter(tags=["donations"])


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    amount_uyu: int = Field(strict=True, ge=1, le=MAX_AMOUNT)
    frequency: Literal["once"] = "once"


def private_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


def session_digest(value):
    try:
        return browser_digest(value)
    except PaymentError as exc:
        raise HTTPException(401, "No pudimos reconocer este navegador. Recargá la página de aportes.") from exc


def owned_donation(db, identity, key):
    digest = session_digest(key)
    donation = db.get(Donation, identity)
    if donation is None or not hmac.compare_digest(donation.browser_key_hash, digest):
        raise HTTPException(404, "No pudimos consultar ese aporte desde este navegador.")
    return donation


@router.get("/payments/config")
def configuration(response: Response):
    private_headers(response)
    return {"enabled": settings.mp_enabled, "environment": settings.mp_environment, "currency": "UYU", "monthly_enabled": False}


@router.post("/payments/checkout")
def checkout(payload: CheckoutRequest, response: Response, db=Depends(get_db), browser_key: str | None = Header(default=None, alias="X-Donation-Session")):
    private_headers(response)
    if not settings.mp_enabled:
        raise HTTPException(503, "Los aportes no están habilitados por ahora. Intentá más adelante.")
    digest = session_digest(browser_key)
    query = select(Donation).where(Donation.request_id == payload.request_id)
    donation = db.scalar(query)
    if donation is None:
        try:
            with db.begin_nested():
                donation = Donation(request_id=payload.request_id, browser_key_hash=digest,
                    amount_uyu=payload.amount_uyu, environment=settings.mp_environment,
                    collector_id=settings.mp_collector_id, application_id=settings.mp_application_id,
                    public_base_url=settings.mp_public_base_url.rstrip("/"))
                db.add(donation)
                db.flush()
        except IntegrityError:
            donation = db.scalar(query)
    if donation is None or not hmac.compare_digest(donation.browser_key_hash, digest):
        raise HTTPException(409, "No pudimos retomar esta solicitud. Volvé a elegir el aporte.")
    if (donation.amount_uyu != payload.amount_uyu or donation.environment != settings.mp_environment
            or donation.collector_id != settings.mp_collector_id or donation.application_id != settings.mp_application_id):
        raise HTTPException(409, "La solicitud anterior corresponde a otro aporte. Volvé a elegir el monto.")
    # Persist the immutable intent before the provider can send its first webhook.
    db.commit()
    donation = db.scalar(query.with_for_update().execution_options(populate_existing=True))
    if donation.provider_order_id:
        target = checked_checkout({"checkout_url": donation.checkout_url}, donation.provider_order_id) if donation.status in {"CREATING", "PENDING"} else None
        return {"donation_id": donation.id, "checkout_url": target, "environment": donation.environment}
    if aware(donation.created_at) < utcnow() - timedelta(hours=1):
        raise HTTPException(409, "Esta solicitud venció. Volvé a elegir el aporte para comenzar otra.")
    try:
        data = MercadoPago().create_order(donation)
        identity = validate_order(donation, data)
        url = checked_checkout(data, identity)
        donation.provider_order_id = identity
        donation.checkout_url = url
        donation.status = "PENDING"
        donation.last_error = None
        db.commit()
    except PaymentError as exc:
        donation.last_error = exc.code
        db.commit()
        raise HTTPException(503, "No pudimos abrir Mercado Pago. Intentá de nuevo; no registramos el aporte como recibido.") from exc
    # Do not invert the queue -> donation locking order used by reconciliation.
    enqueue(db, identity, donation.environment)
    db.commit()
    return {"donation_id": donation.id, "checkout_url": url, "environment": donation.environment}


@router.get("/payments/donations/{donation_id}")
def donation_status(donation_id: UUID, response: Response, db=Depends(get_db), browser_key: str | None = Header(default=None, alias="X-Donation-Session")):
    private_headers(response)
    row = owned_donation(db, donation_id, browser_key)
    return {"id": row.id, "amount_uyu": row.amount_uyu, "currency": "UYU", "status": row.status,
        "environment": row.environment, "updated_at": row.updated_at, "confirmed_at": row.confirmed_at}


@router.post("/payments/donations/{donation_id}/refresh")
def refresh_donation(donation_id: UUID, response: Response, db=Depends(get_db), browser_key: str | None = Header(default=None, alias="X-Donation-Session")):
    private_headers(response)
    row = owned_donation(db, donation_id, browser_key)
    if row.environment != settings.mp_environment or not settings.mp_configured:
        raise HTTPException(503, "No podemos actualizar este aporte por ahora.")
    if row.provider_order_id:
        enqueue(db, row.provider_order_id, row.environment)
        db.commit()
    return {"ok": True}


@router.post("/payments/mercadopago/webhook")
def webhook(request: Request, db=Depends(get_db)):
    if not settings.mp_configured:
        raise HTTPException(503, "Recepción de aportes desactivada.")
    ids = request.query_params.getlist("data.id")
    signatures = request.headers.getlist("x-signature")
    request_ids = request.headers.getlist("x-request-id")
    if (len(ids) != 1 or len(signatures) != 1 or len(request_ids) != 1
            or not validate_signature(ids[0], signatures[0], request_ids[0])):
        raise HTTPException(401, "Notificación no válida.")
    topics = request.query_params.getlist("type")
    if len(topics) > 1 or (topics and topics[0] not in {"order", "orders_v2"}):
        return {"ok": True}
    if not mode_matches(ids[0], settings.mp_environment):
        raise HTTPException(400, "Entorno de notificación no válido.")
    # Body, payer, status and amount from the event are deliberately not trusted.
    enqueue(db, ids[0], settings.mp_environment)
    db.commit()
    return {"ok": True}


@router.get("/admin/donations")
def admin_donations(response: Response, environment: Literal["test", "production"] = "production",
    state: Literal["all", "CREATING", "PENDING", "APPROVED", "REJECTED", "CANCELLED", "REFUNDED", "PARTIALLY_REFUNDED", "CHARGEBACK"] = "all",
    from_at: AwareDatetime | None = None, to_at: AwareDatetime | None = None,
    limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0, le=10000),
    db=Depends(get_db), user=Depends(administrator)):
    private_headers(response)
    filters = [Donation.environment == environment, *period_filters(Donation.created_at, from_at, to_at)]
    summary = dict(db.execute(select(Donation.status, func.count()).where(*filters).group_by(Donation.status)).all())
    approved = db.scalar(select(func.coalesce(func.sum(Donation.amount_uyu), 0)).where(*filters, Donation.status == "APPROVED"))
    if state != "all":
        filters.append(Donation.status == state)
    total = db.scalar(select(func.count()).select_from(Donation).where(*filters)) or 0
    rows = db.scalars(select(Donation).where(*filters).order_by(Donation.created_at.desc(), Donation.id).offset(offset).limit(limit))
    queue_filters = [DonationSync.environment == environment, DonationSync.pending.is_(True)]
    queued = db.scalar(select(func.count()).select_from(DonationSync).where(*queue_filters)) or 0
    retries = db.scalar(select(func.count()).select_from(DonationSync).where(*queue_filters, DonationSync.last_error.is_not(None))) or 0
    return {"items": [{"id": row.id, "amount_uyu": row.amount_uyu, "status": row.status, "environment": row.environment,
        "created_at": row.created_at, "confirmed_at": row.confirmed_at, "last_synced_at": row.last_synced_at,
        "provider_order_id": row.provider_order_id, "last_error": row.last_error} for row in rows],
        "summary": summary, "approved_amount_uyu": str(int(approved)), "total": total, "limit": limit, "offset": offset,
        "queue": {"pending": queued, "retrying": retries}, "enabled": settings.mp_enabled,
        "active_environment": settings.mp_environment, "generated_at": utcnow()}
