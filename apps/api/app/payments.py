"""Hosted Checkout Pro via Orders API. Credentials and payment evidence stay server-side."""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import hmac
import logging
import re
import time
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx2 as httpx
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.analysis.service import utcnow
from app.core.config import settings
from app.db.session import SessionLocal
from app.matching.linked import aware
from app.models import Donation, DonationSync

ORDER_ID = re.compile(r"ORD[A-Z0-9]{20,50}\Z")
BROWSER_KEY = re.compile(r"[A-Za-z0-9_-]{43}\Z")
MAX_AMOUNT = 9007199254740991


class PaymentError(Exception):
    """Only a fixed safe code may leave the adapter; never provider bodies or headers."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class MercadoPago:
    def request(self, method, path, *, body=None, key=None):
        headers = {"Authorization": f"Bearer {settings.mp_access_token.get_secret_value()}", "Accept": "application/json"}
        if key:
            headers["X-Idempotency-Key"] = str(key)
        try:
            with httpx.Client(timeout=httpx.Timeout(10, connect=3), follow_redirects=False, trust_env=False) as client:
                response = client.request(method, "https://api.mercadopago.com" + path, headers=headers, json=body)
            if response.status_code not in {200, 201}:
                raise PaymentError("PROVIDER_CREDENTIALS" if response.status_code in {401, 403} else "PROVIDER_UNAVAILABLE" if response.status_code >= 500 or response.status_code == 429 else "PROVIDER_REJECTED")
            data = response.json()
            if not isinstance(data, dict):
                raise PaymentError("INVALID_PROVIDER_RESPONSE")
            return data
        except (httpx.HTTPError, ValueError) as exc:
            raise PaymentError("PROVIDER_UNAVAILABLE") from exc

    def create_order(self, donation):
        target = f"{donation.public_base_url}/apoyanos/resultado?aporte={donation.id}"
        return self.request("POST", "/v1/orders", key=donation.id, body={
            "type": "online", "processing_mode": "manual", "capture_mode": "automatic_async",
            "total_amount": f"{donation.amount_uyu}.00", "external_reference": str(donation.id),
            "description": "Aporte voluntario puntual a MascoMatch", "expiration_time": "P1D",
            "items": [{"title": "Aporte voluntario a MascoMatch", "quantity": 1, "unit_price": f"{donation.amount_uyu}.00"}],
            "config": {"online": {"success_url": target, "failure_url": target, "pending_url": target, "auto_return": "all", "retries": {"allowed": False}}, "payment_method": {"max_installments": 1}},
        })

    def get_order(self, identity):
        if not ORDER_ID.fullmatch(identity):
            raise PaymentError("INVALID_ORDER_ID")
        return self.request("GET", f"/v1/orders/{identity}")


def browser_digest(key):
    if not key or not BROWSER_KEY.fullmatch(key):
        raise PaymentError("BROWSER_SESSION_REQUIRED")
    return sha256(key.encode()).hexdigest()


def validate_signature(identity, signature, request_id, now=None):
    if (not ORDER_ID.fullmatch(identity) or not request_id or len(request_id) > 160
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", request_id) or not signature or len(signature) > 1024):
        return False
    fields = {}
    for part in signature.split(","):
        pair = part.strip().split("=", 1)
        if len(pair) != 2 or pair[0] in fields:
            return False
        fields[pair[0]] = pair[1]
    stamp, digest = fields.get("ts", ""), fields.get("v1", "")
    if not re.fullmatch(r"[0-9]{10}|[0-9]{13}", stamp) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        return False
    timestamp = int(stamp) / (1000 if len(stamp) == 13 else 1)
    if abs((time.time() if now is None else now) - timestamp) > 300:
        return False
    # Preserve data.id case: the current Orders contract uses uppercase IDs.
    manifest = f"id:{identity};request-id:{request_id};ts:{stamp};"
    expected = hmac.new(settings.mp_webhook_secret.get_secret_value().encode(), manifest.encode(), sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def mode_matches(identity, environment):
    return bool(ORDER_ID.fullmatch(identity)) and identity.startswith("ORDTST") == (environment == "test")


def money(value):
    try:
        if isinstance(value, (float, bool)):
            raise InvalidOperation
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PaymentError("INVALID_PROVIDER_AMOUNT") from exc


def validate_order(donation, data):
    identity = str(data.get("id", ""))
    if not mode_matches(identity, donation.environment):
        raise PaymentError("ENVIRONMENT_MISMATCH")
    if donation.provider_order_id and identity != donation.provider_order_id:
        raise PaymentError("ORDER_MISMATCH")
    integration = data.get("integration_data")
    if not isinstance(integration, dict):
        raise PaymentError("PAYMENT_MISMATCH")
    if (str(data.get("external_reference")) != str(donation.id)
            or str(data.get("user_id")) != donation.collector_id
            or str(integration.get("application_id")) != donation.application_id
            or data.get("currency") != "UYU" or data.get("country_code") != "URY"
            or data.get("type") != "online" or money(data.get("total_amount")) != Decimal(donation.amount_uyu)):
        raise PaymentError("PAYMENT_MISMATCH")
    return identity


def checked_checkout(data, identity):
    value = data.get("checkout_url")
    if not isinstance(value, str) or len(value) > 2048:
        raise PaymentError("INVALID_CHECKOUT_URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise PaymentError("INVALID_CHECKOUT_URL") from exc
    if (parsed.scheme != "https" or parsed.hostname not in {"www.mercadopago.com.uy", "mercadopago.com.uy"}
            or parsed.username or parsed.password or port not in {None, 443}
            or not parsed.path.startswith("/checkout/") or parse_qs(parsed.query).get("order_id") != [identity]):
        raise PaymentError("INVALID_CHECKOUT_URL")
    return value


def enqueue(db, identity, environment):
    now = utcnow()
    query = select(DonationSync).where(DonationSync.provider_order_id == identity, DonationSync.environment == environment)
    job = db.scalar(query.with_for_update())
    if job is None:
        try:
            with db.begin_nested():
                job = DonationSync(provider_order_id=identity, environment=environment, available_at=now, received_at=now)
                db.add(job)
                db.flush()
        except IntegrityError:
            job = db.scalar(query.with_for_update())
    job.pending = True
    job.received_at = now
    job.available_at = now
    return job


def apply_order(donation, data):
    validate_order(donation, data)
    try:
        updated = aware(datetime.fromisoformat(data["last_updated_date"].replace("Z", "+00:00")))
    except (ValueError, KeyError, TypeError) as exc:
        raise PaymentError("INVALID_PROVIDER_DATE") from exc
    if donation.provider_updated_at and updated < aware(donation.provider_updated_at):
        return
    status, detail = data.get("status"), data.get("status_detail")
    states = {"created": "PENDING", "processing": "PENDING", "action_required": "PENDING", "failed": "REJECTED", "canceled": "CANCELLED", "refunded": "REFUNDED", "charged_back": "CHARGEBACK"}
    if status == "processed" and detail in {"accredited", "partially_refunded"}:
        paid = money(data.get("total_paid_amount"))
        if paid > Decimal(donation.amount_uyu) or detail == "accredited" and paid != Decimal(donation.amount_uyu):
            raise PaymentError("PAID_AMOUNT_MISMATCH")
        state = "PARTIALLY_REFUNDED" if detail == "partially_refunded" else "APPROVED"
        if donation.confirmed_at is None:
            donation.confirmed_at = utcnow()
    elif status in states:
        state = states[status]
    else:
        raise PaymentError("UNKNOWN_PROVIDER_STATE")
    donation.provider_order_id = data["id"]
    donation.provider_updated_at = updated
    donation.provider_status = status
    donation.provider_status_detail = detail if isinstance(detail, str) and len(detail) <= 80 else None
    donation.status = state
    donation.last_error = None


def sync_pending(factory=None, provider=None):
    if not settings.mp_configured:
        return 0
    factory, provider = factory or SessionLocal, provider or MercadoPago()
    with factory() as db:
        ids = list(db.scalars(select(DonationSync.id).where(DonationSync.pending.is_(True), DonationSync.environment == settings.mp_environment, DonationSync.available_at <= utcnow()).order_by(DonationSync.available_at).limit(10)))
    processed = 0
    for identity in ids:
        with factory() as db:
            job = db.scalar(select(DonationSync).where(DonationSync.id == identity).with_for_update(skip_locked=True))
            if not job or not job.pending or aware(job.available_at) > utcnow():
                continue
            job.attempts += 1
            donation = None
            try:
                data = provider.get_order(job.provider_order_id)
                try:
                    reference = UUID(str(data.get("external_reference", "")))
                except ValueError:
                    reference = None
                donation = db.scalar(select(Donation).where(Donation.id == reference).with_for_update()) if reference else None
                if donation and donation.environment == job.environment:
                    if str(data.get("id")) != job.provider_order_id:
                        raise PaymentError("ORDER_MISMATCH")
                    apply_order(donation, data)
                    donation.last_synced_at = utcnow()
                job.pending = False
                job.last_error = None
                job.processed_at = utcnow()
                processed += 1
            except PaymentError as exc:
                if donation is not None:
                    donation.last_error = exc.code
                job.last_error = exc.code
                job.available_at = utcnow() + timedelta(seconds=min(3600, 15 * 2 ** min(job.attempts, 8)))
                # Keep retrying; neither a provider outage nor an unverified event means paid.
                logging.getLogger(__name__).warning("donation_sync_retry code=%s", exc.code)
            db.commit()
    return processed


def enqueue_overdue(factory=None):
    if not settings.mp_configured:
        return
    with (factory or SessionLocal)() as db:
        now = utcnow()
        # Recovery for a missing notification; webhooks remain the primary path.
        pending = (Donation.status.in_(["CREATING", "PENDING"]) &
            (Donation.created_at >= now - timedelta(days=30)) &
            or_(Donation.last_synced_at.is_(None), Donation.last_synced_at < now - timedelta(minutes=15)))
        settled = (Donation.status.in_(["APPROVED", "PARTIALLY_REFUNDED"]) &
            (Donation.created_at >= now - timedelta(days=90)) &
            (Donation.last_synced_at < now - timedelta(days=1)))
        rows = db.scalars(select(Donation).where(Donation.environment == settings.mp_environment,
            Donation.provider_order_id.is_not(None), Donation.created_at < now - timedelta(minutes=2),
            or_(pending, settled)).order_by(Donation.last_synced_at.asc().nullsfirst()).limit(10))
        for row in rows:
            job = db.scalar(select(DonationSync).where(DonationSync.provider_order_id == row.provider_order_id, DonationSync.environment == row.environment))
            if job is None or not job.pending:
                enqueue(db, row.provider_order_id, row.environment)
        db.commit()


async def reconciliation_loop():
    while True:
        try:
            await asyncio.to_thread(enqueue_overdue)
            await asyncio.to_thread(sync_pending)
        except Exception:
            logging.getLogger(__name__).warning("donation_reconciliation_unavailable")
        await asyncio.sleep(5)
