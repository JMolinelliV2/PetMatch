import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app import models  # noqa: F401
from app.core.config import settings


@pytest.fixture(autouse=True)
def clear_model_metadata():
    from app.analysis.providers import clear_capability_cache
    clear_capability_cache()
    yield
    clear_capability_cache()


@pytest.fixture()
def confirm_account(client,db_factory):
    def confirm(email):
        from sqlalchemy import select
        from app.account_mail import decrypt_token
        with db_factory() as db:
            ticket=db.scalar(select(models.AccountToken).join(models.User,models.AccountToken.user_id==models.User.id).where(models.User.email==email,models.AccountToken.kind=="VERIFY_EMAIL"))
            code=decrypt_token(ticket.encrypted_token)
        assert client.post("/api/v1/auth/verify-email",json={"code":code}).status_code==200
    return confirm


@pytest.fixture()
def db_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    yield TestingSession
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(db_factory, monkeypatch):
    # No Redis or model request is started by the test application lifespan.
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "embeddings_enabled", False)
    monkeypatch.setattr(settings, "mail_group_seconds", 0)
    # Account recovery requires delivery enabled; delivery loops remain idle here.
    monkeypatch.setattr(settings, "mail_delivery_mode", "smtp")
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    async def idle_worker():
        await asyncio.Event().wait()
    monkeypatch.setattr("app.matching.linked.reconciliation_loop", idle_worker)
    monkeypatch.setattr("app.notifications.email.delivery_loop", idle_worker)
    monkeypatch.setattr("app.matching.engine.general_matching_loop", idle_worker)
    monkeypatch.setattr("app.account_mail.delivery_loop", idle_worker)
    monkeypatch.setattr("app.photo_reminders.delivery_loop", idle_worker)
    monkeypatch.setattr("app.account_management.cleanup_loop", idle_worker)
    monkeypatch.setattr("app.contact_mail.delivery_loop", idle_worker)
    monkeypatch.setattr("app.operational_tracking.cleanup_loop", idle_worker)
    monkeypatch.setattr("app.product_analytics.cleanup_loop", idle_worker)

    def override_get_db():
        db = db_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def unverified_headers(client):
    response = client.post("/api/v1/auth/register", json={"email": "owner@example.com", "password": "a-strong-passphrase", "name": "Owner"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def auth_headers(client, unverified_headers, db_factory):
    # Publish fixtures exercise the real confirmation flow, not a bypass of the guard.
    from sqlalchemy import select
    from app.account_mail import decrypt_token
    with db_factory() as db:
        ticket = db.scalar(select(models.AccountToken).where(models.AccountToken.kind == "VERIFY_EMAIL"))
        code = decrypt_token(ticket.encrypted_token)
    assert client.post("/api/v1/auth/verify-email", json={"code": code}).status_code == 200
    return unverified_headers

