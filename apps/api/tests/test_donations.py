"""Payment trust boundaries, with isolated SQLite and a provider double; no real charges."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import hmac
import time
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.analysis.service import utcnow
from app.core.config import settings
from app.models import Donation, DonationSync
from app.payments import PaymentError, apply_order, sync_pending, validate_signature
from app.routers import donations

KEY = "a" * 43
HEADERS = {"X-Donation-Session": KEY}


class Provider:
    def __init__(self):
        self.orders = {}
        self.creations = []
        self.fail_next = False
        self.override = {}

    def create_order(self, donation):
        self.creations.append(donation.id)
        if self.fail_next:
            self.fail_next = False
            raise PaymentError("PROVIDER_UNAVAILABLE")
        identity = "ORDTST" + donation.id.hex.upper()
        data = {"id": identity, "type": "online", "currency": "UYU", "country_code": "URY",
            "user_id": settings.mp_collector_id, "integration_data": {"application_id": settings.mp_application_id},
            "external_reference": str(donation.id), "total_amount": str(donation.amount_uyu),
            "total_paid_amount": "0", "status": "created", "status_detail": "created",
            "last_updated_date": utcnow().isoformat(), "checkout_url": f"https://www.mercadopago.com.uy/checkout/v1/redirect?order_id={identity}"}
        data.update(self.override)
        self.orders[data["id"]] = deepcopy(data)
        return deepcopy(data)

    def get_order(self, identity):
        return deepcopy(self.orders[identity])


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "mp_enabled", True)
    monkeypatch.setattr(settings, "mp_environment", "test")
    monkeypatch.setattr(settings, "mp_collector_id", "12345")
    monkeypatch.setattr(settings, "mp_application_id", "67890")
    monkeypatch.setattr(settings, "mp_public_base_url", "https://mascomatch.example")
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "mp_access_token", SecretStr("only-a-fake-access-token-12345"))
    monkeypatch.setattr(settings, "mp_webhook_secret", SecretStr("only-for-local-verification-12345"))
    fake = Provider()
    monkeypatch.setattr(donations, "MercadoPago", lambda: fake)
    return fake


def payload(amount=100, identity=None):
    return {"amount_uyu": amount, "request_id": str(identity or uuid4()), "frequency": "once"}


def event_headers(identity, stamp=None):
    stamp = str(int(time.time())) if stamp is None else str(stamp)
    request_id = "local-event-1234"
    manifest = f"id:{identity};request-id:{request_id};ts:{stamp};"
    digest = hmac.new(settings.mp_webhook_secret.get_secret_value().encode(), manifest.encode(), sha256).hexdigest()
    return {"x-request-id": request_id, "x-signature": f"ts={stamp},v1={digest}"}


def test_disabled_checkout_never_contacts_provider(client, monkeypatch):
    monkeypatch.setattr(settings, "mp_enabled", False)
    assert client.get("/api/v1/payments/config").json()["monthly_enabled"] is False
    assert client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload()).status_code == 503


def test_checkout_is_idempotent_and_receipt_is_private(client, provider, db_factory):
    body = payload()
    first = client.post("/api/v1/payments/checkout", headers=HEADERS, json=body)
    assert first.status_code == 200
    again = client.post("/api/v1/payments/checkout", headers=HEADERS, json=body)
    assert again.json() == first.json() and len(provider.creations) == 1
    reference = first.json()["donation_id"]
    url = f"/api/v1/payments/donations/{reference}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-Donation-Session": "b" * 43}).status_code == 404
    receipt = client.get(url + "?status=approved&payment_id=1234", headers=HEADERS)
    assert receipt.status_code == 200 and receipt.json()["status"] == "PENDING"
    assert set(receipt.json()) == {"id", "amount_uyu", "currency", "status", "environment", "updated_at", "confirmed_at"}
    assert client.post("/api/v1/payments/checkout", headers=HEADERS, json={**body, "amount_uyu": 300}).status_code == 409
    assert client.post("/api/v1/payments/checkout", headers={"X-Donation-Session": "b" * 43}, json=body).status_code == 409
    with db_factory() as db:
        row = db.scalar(select(Donation))
        assert row.browser_key_hash == sha256(KEY.encode()).hexdigest()
        assert db.scalar(select(func.count()).select_from(Donation)) == 1


@pytest.mark.parametrize("amount", [0, -1, True, 1.5, "100", 9007199254740992])
def test_invalid_amounts_never_create_orders(client, provider, amount):
    assert client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload(amount)).status_code == 422
    assert not provider.creations


def test_monthly_or_unknown_fields_are_rejected(client, provider):
    assert client.post("/api/v1/payments/checkout", headers=HEADERS, json={**payload(), "frequency": "monthly"}).status_code == 422
    assert client.post("/api/v1/payments/checkout", headers=HEADERS, json={**payload(), "currency": "USD"}).status_code == 422
    assert not provider.creations


def test_ambiguous_provider_timeout_reuses_the_same_intent(client, provider, db_factory):
    provider.fail_next = True
    body = payload()
    assert client.post("/api/v1/payments/checkout", headers=HEADERS, json=body).status_code == 503
    assert client.post("/api/v1/payments/checkout", headers=HEADERS, json=body).status_code == 200
    assert provider.creations[0] == provider.creations[1]
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Donation)) == 1


@pytest.mark.parametrize("override", [{"currency": "USD"}, {"country_code": "ARG"}, {"user_id": "999"}, {"integration_data": {"application_id": "999"}}, {"total_amount": "1"}, {"external_reference": str(uuid4())}, {"id": "ORD" + "A" * 26}, {"checkout_url": "https://evil.example/checkout/"}])
def test_unexpected_provider_checkout_is_never_exposed(client, provider, override):
    provider.override = override
    result = client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload())
    assert result.status_code == 503 and "checkout_url" not in result.json()


def test_signed_webhooks_are_deduplicated_and_body_cannot_confirm_payment(client, provider, db_factory):
    response = client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload())
    identity = next(iter(provider.orders))
    url = f"/api/v1/payments/mercadopago/webhook?data.id={identity}&type=order"
    headers = event_headers(identity)
    forged = {"status": "approved", "data": {"id": "ignored", "status": "approved", "total_paid_amount": "100"}}
    assert client.post(url, headers=headers, json=forged).status_code == 200
    assert client.post(url, headers=headers, json=forged).status_code == 200
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(DonationSync)) == 1
    assert sync_pending(db_factory, provider) == 1
    assert sync_pending(db_factory, provider) == 0
    receipt = f"/api/v1/payments/donations/{response.json()['donation_id']}"
    assert client.get(receipt, headers=HEADERS).json()["status"] == "PENDING"
    provider.orders[identity].update(status="processed", status_detail="accredited", total_paid_amount="100", last_updated_date=utcnow().isoformat())
    assert client.post(url, headers=headers, json={}).status_code == 200
    assert sync_pending(db_factory, provider) == 1
    saved = client.get(receipt, headers=HEADERS).json()
    assert saved["status"] == "APPROVED" and saved["confirmed_at"] is not None
    assert client.post(url, headers=headers, json={}).status_code == 200
    sync_pending(db_factory, provider)
    assert client.get(receipt, headers=HEADERS).json()["confirmed_at"] == saved["confirmed_at"]


def test_invalid_stale_and_ambiguous_signatures_do_not_enqueue(client, provider, db_factory):
    identity = "ORDTST" + "A" * 26
    url = f"/api/v1/payments/mercadopago/webhook?data.id={identity}&type=order"
    assert client.post(url, json={}).status_code == 401
    assert client.post(url, headers=event_headers(identity, int(time.time()) - 600), json={}).status_code == 401
    assert client.post(url + f"&data.id={identity}", headers=event_headers(identity), json={}).status_code == 401
    changed = event_headers(identity)
    changed["x-signature"] += ",ts=1234567890"
    assert client.post(url, headers=changed, json={}).status_code == 401
    for stamp in [int(time.time()), int(time.time() * 1000)]:
        headers = event_headers(identity, stamp)
        assert validate_signature(identity, headers["x-signature"], headers["x-request-id"])
        assert not validate_signature(identity.lower(), headers["x-signature"], headers["x-request-id"])
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(DonationSync)) == 0


def test_amount_mismatch_retries_without_confirming(client, provider, db_factory):
    result = client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload())
    identity = next(iter(provider.orders))
    provider.orders[identity].update(status="processed", status_detail="accredited", total_paid_amount="99")
    assert sync_pending(db_factory, provider) == 0
    with db_factory() as db:
        row = db.scalar(select(DonationSync))
        assert row.pending and row.last_error == "PAID_AMOUNT_MISMATCH"
    assert client.get(f"/api/v1/payments/donations/{result.json()['donation_id']}", headers=HEADERS).json()["status"] == "PENDING"


def test_refunds_and_older_updates_do_not_restore_an_approved_balance(client, provider, db_factory):
    client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload())
    identity = next(iter(provider.orders))
    now = utcnow()
    with db_factory() as db:
        row = db.scalar(select(Donation))
        original = {**provider.orders[identity], "status": "processed", "status_detail": "accredited", "total_paid_amount": "100", "last_updated_date": now.isoformat()}
        apply_order(row, original)
        assert row.status == "APPROVED"
        apply_order(row, {**original, "status_detail": "partially_refunded", "total_paid_amount": "60", "last_updated_date": (now + timedelta(seconds=1)).isoformat()})
        assert row.status == "PARTIALLY_REFUNDED"
        apply_order(row, {**original, "status": "refunded", "status_detail": "refunded", "total_paid_amount": "0", "last_updated_date": (now + timedelta(seconds=2)).isoformat()})
        assert row.status == "REFUNDED"
        apply_order(row, original)
        assert row.status == "REFUNDED"


def test_admin_data_requires_admin_permissions(client, provider, auth_headers):
    assert client.get("/api/v1/admin/donations").status_code == 401
    assert client.get("/api/v1/admin/donations", headers=auth_headers).status_code == 403


def test_oversized_webhook_is_rejected_before_enqueue(client, provider):
    assert client.post("/api/v1/payments/mercadopago/webhook", content=b"x" * 32769).status_code == 413


def test_admin_totals_separate_test_and_real_money_and_exclude_refunds(client, provider, db_factory):
    from app.admin_access import administrator
    from app.main import app
    client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload())
    with db_factory() as db:
        db.scalar(select(Donation)).status = "APPROVED"
        for amount, status in [(200, "APPROVED"), (50, "REFUNDED"), (300, "PENDING")]:
            db.add(Donation(request_id=uuid4(), browser_key_hash=sha256(KEY.encode()).hexdigest(),
                amount_uyu=amount, status=status, environment="production", collector_id="12345",
                application_id="67890", public_base_url="https://mascomatch.example"))
        db.commit()
    app.dependency_overrides[administrator] = lambda: object()
    try:
        live = client.get("/api/v1/admin/donations").json()
        assert live["approved_amount_uyu"] == "200" and live["total"] == 3
        assert live["summary"]["APPROVED"] == 1
        test = client.get("/api/v1/admin/donations?environment=test").json()
        assert test["approved_amount_uyu"] == "100" and test["total"] == 1
        assert client.get("/api/v1/admin/donations?state=REFUNDED").json()["total"] == 1
        assert client.get("/api/v1/admin/donations", params={"from_at": (utcnow() + timedelta(days=1)).isoformat()}).json()["approved_amount_uyu"] == "0"
        assert "browser_key_hash" not in str(live) and "collector_id" not in str(live)
    finally:
        app.dependency_overrides.pop(administrator)


def test_pausing_new_checkouts_keeps_existing_payment_confirmation_working(client, provider, db_factory, monkeypatch):
    result = client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload())
    identity = next(iter(provider.orders))
    provider.orders[identity].update(status="processed", status_detail="accredited", total_paid_amount="100", last_updated_date=utcnow().isoformat())
    monkeypatch.setattr(settings, "mp_enabled", False)
    assert client.get("/api/v1/payments/config").json()["enabled"] is False
    assert client.post("/api/v1/payments/checkout", headers=HEADERS, json=payload()).status_code == 503
    url = f"/api/v1/payments/mercadopago/webhook?data.id={identity}&type=order"
    assert client.post(url, headers=event_headers(identity), json={}).status_code == 200
    assert sync_pending(db_factory, provider) == 1
    assert client.get(f"/api/v1/payments/donations/{result.json()['donation_id']}", headers=HEADERS).json()["status"] == "APPROVED"
