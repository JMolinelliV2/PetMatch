from datetime import timedelta
import json
from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest
from sqlalchemy import func, select

from app.analysis import tasks
from app.analysis.service import schedule_photo, utcnow
from app.core.config import Settings, settings
from app.matching import linked
from app.models import AnalysisJob, FeatureSet, LostCase, Notification, Observation, Photo
from app.notifications import email


def lost_notice(client, headers, *, species="dog"):
    pet = client.post("/api/v1/pets", headers=headers, json={"name": "Luna", "species": species, "primary_color": "brown", "size": "medium"}).json()
    case = client.post("/api/v1/lost-cases", headers=headers, json={"pet_id": pet["id"], "lost_at": (utcnow() - timedelta(hours=2)).isoformat(), "latitude": -34.9, "longitude": -56.15, "description": "Descripción del dueño, que no debe copiarse al avistamiento."}).json()
    return pet, case


def data(**changes):
    return {"request_id": str(uuid4()), "observed_at": (utcnow() - timedelta(minutes=5)).isoformat(), "latitude": "-34.90123", "longitude": "-56.15234", "public_location": "Montevideo, Uruguay", **changes}


def submit(client, case, payload=None, files=None, headers=None):
    return client.post(f"/api/v1/public/lost-animals/{case['id']}/sightings", data=payload or data(), files=files, headers=headers)


def mock_storage(monkeypatch):
    from app.routers import linked_sightings
    keys = []
    def store(owner_type, identity, mime, payload):
        key = f"{owner_type}/{identity}/{uuid4()}.jpg"
        keys.append(key)
        return key, 10, 10
    monkeypatch.setattr(linked_sightings, "store_private_image", store)
    monkeypatch.setattr(linked_sightings, "delete_private_image", lambda key: None)
    return keys


def feature_set(db, job, **traits):
    features = {name: {"value": value, "confidence": .95, "source": "image"} for name, value in traits.items()}
    job.status = "SUCCEEDED"
    db.add(FeatureSet(analysis_job_id=job.id, features=features))
    db.flush()


def test_anonymous_linked_sighting_only_needs_location_and_date(client, auth_headers, db_factory, monkeypatch):
    _, case = lost_notice(client, auth_headers)
    monkeypatch.setattr(settings, "ai_enabled", True)
    payload = data()
    response = submit(client, case, payload)
    assert response.status_code == 201
    assert response.json()["status"] == "UNVERIFIED"
    assert response.json()["owner_notified"] is True
    with db_factory() as db:
        observation = db.get(Observation, UUID(response.json()["id"]))
        assert observation.author_id is None
        assert str(observation.linked_case_id) == case["id"]
        assert "Descripción del dueño" not in observation.description
        assert observation.sex == "unknown"
        assert db.scalar(select(func.count()).select_from(AnalysisJob)) == 0
    status = client.get(f"/api/v1/public/lost-animals/{case['id']}/sightings/{response.json()['id']}/status").json()
    assert set(status) == {"id", "public_id", "status", "owner_notified"}
    notifications = client.get("/api/v1/notifications", headers=auth_headers)
    assert notifications.status_code == 200
    assert notifications.headers["cache-control"] == "no-store"
    notice = notifications.json()["items"][0]
    assert notice["kind"] == "REPORTED_SIGHTING"
    assert notice["latitude"] == -34.90123
    assert "por confirmar" in notice["body"]
    assert notice["photo_ids"] == []
    assert client.get(f"/api/v1/observations/{response.json()['id']}").json()["latitude"] == -34.9


def test_sighting_and_notification_are_idempotent(client, auth_headers, db_factory):
    _, case = lost_notice(client, auth_headers)
    payload = data()
    first = submit(client, case, payload)
    second = submit(client, case, payload)
    assert first.json() == second.json()
    assert submit(client, case, {**payload, "latitude": "-34.902"}).status_code == 409
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 1
        assert db.scalar(select(func.count()).select_from(Notification)) == 1


@pytest.mark.parametrize("changes,status", [({"latitude": "nan"}, 422), ({"longitude": "181"}, 422), ({"observed_at": "2099-01-01T00:00:00Z"}, 422), ({"latitude": "-33"}, 201), ({"observed_at": "2020-01-01T00:00:00Z"}, 201)])
def test_invalid_payloads_are_rejected_and_accepted_incompatible_reports_notify(client, auth_headers, changes, status):
    _, case = lost_notice(client, auth_headers)
    response = submit(client, case, data(**changes))
    assert response.status_code == status
    if status == 201:
        assert response.json()["status"] == "NOT_COMPATIBLE"
        assert response.json()["owner_notified"] is True
    assert client.get("/api/v1/notifications", headers=auth_headers).json()["total"] == int(status == 201)


def test_closed_notice_rejects_new_sightings_and_hides_existing_notifications(client, auth_headers, db_factory):
    _, case = lost_notice(client, auth_headers)
    result = submit(client, case).json()
    assert client.get("/api/v1/notifications", headers=auth_headers).json()["total"] == 1
    client.patch(f"/api/v1/lost-cases/{case['id']}", headers=auth_headers, json={"status": "FOUND"})
    assert submit(client, case).status_code == 404
    assert client.get("/api/v1/notifications", headers=auth_headers).json()["total"] == 0
    linked.reconcile_pending(db_factory)
    with db_factory() as db:
        assert db.get(Observation, UUID(result["id"])).matching_status == "INACTIVE"


def test_notification_access_is_scoped_and_read_status_persists(client, auth_headers):
    _, case = lost_notice(client, auth_headers)
    submit(client, case)
    notice = client.get("/api/v1/notifications", headers=auth_headers).json()["items"][0]
    stranger = client.post("/api/v1/auth/register", json={"email": "stranger@example.test", "password": "a-strong-passphrase", "name": "Stranger"}).json()
    stranger_headers = {"Authorization": f"Bearer {stranger['access_token']}"}
    assert client.get("/api/v1/notifications").status_code == 401
    assert client.get("/api/v1/notifications", headers=stranger_headers).json()["items"] == []
    assert client.get(f"/api/v1/notifications/{notice['id']}", headers=stranger_headers).status_code == 404
    assert client.get(f"/api/v1/notifications/{notice['id']}", headers=auth_headers).json()["id"] == notice["id"]
    path = f"/api/v1/notifications/{notice['id']}/read"
    assert client.patch(path, headers=stranger_headers).status_code == 404
    assert client.patch(path, headers=auth_headers).json()["read_at"] is not None
    assert client.get("/api/v1/notifications", headers=auth_headers).json()["unread_count"] == 0
    assert client.patch(path, headers=auth_headers).status_code == 200


def test_owner_does_not_receive_alert_for_their_own_sighting(client, auth_headers):
    _, case = lost_notice(client, auth_headers)
    response = submit(client, case, headers=auth_headers)
    assert response.status_code == 201
    assert not response.json()["owner_notified"]


@pytest.mark.parametrize("species,color,expected", [("dog", "brown", "UNVERIFIED"), ("cat", "brown", "NOT_COMPATIBLE"), ("dog", "white", "NOT_COMPATIBLE"), ("dog", "unknown", "UNVERIFIED")])
def test_photo_traits_alone_do_not_assert_identity(client, auth_headers, db_factory, monkeypatch, species, color, expected):
    _, case = lost_notice(client, auth_headers)
    mock_storage(monkeypatch)
    monkeypatch.setattr(settings, "ai_enabled", True)
    response = submit(client, case, files=[("photos", ("dog.jpg", b"photo", "image/jpeg"))])
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"
    with db_factory() as db:
        job = db.scalar(select(AnalysisJob).where(AnalysisJob.owner_type == "observation"))
        assert job.source_type == "image"
        feature_set(db, job, species=species, primary_color=color)
        linked.evaluate_sighting(db, UUID(response.json()["id"]))
        db.commit()
    linked.reconcile_related("observation", UUID(response.json()["id"]), db_factory)
    with db_factory() as db:
        assert db.get(Observation, UUID(response.json()["id"])).matching_status == expected
        assert db.scalar(select(func.count()).select_from(Notification)) == 1
    if expected == "POSSIBLE_MATCH":
        notice = client.get("/api/v1/notifications", headers=auth_headers).json()["items"][0]
        assert notice["kind"] == "POSSIBLE_MATCH"
        assert len(notice["photo_ids"]) == 1
        assert "Color compatible" in notice["reasons"]


def test_photo_comparison_waits_for_all_images_and_hides_unrelated_photos(client, auth_headers, db_factory, monkeypatch):
    _, case = lost_notice(client, auth_headers)
    mock_storage(monkeypatch)
    monkeypatch.setattr(settings, "ai_enabled", True)
    response = submit(client, case, files=[("photos", (f"{index}.jpg", b"photo", "image/jpeg")) for index in range(2)])
    identity = UUID(response.json()["id"])
    with db_factory() as db:
        jobs = list(db.scalars(select(AnalysisJob).where(AnalysisJob.owner_id == identity)))
        feature_set(db, jobs[0], species="dog", primary_color="brown")
        assert linked.evaluate_sighting(db, identity) == "PENDING"
        feature_set(db, jobs[1], species="dog", primary_color="brown")
        assert linked.evaluate_sighting(db, identity) == "UNVERIFIED"
        db.commit()
    notice = client.get("/api/v1/notifications", headers=auth_headers).json()["items"][0]
    from app.routers import notifications
    monkeypatch.setattr(notifications, "load_analysis_image", lambda key, mime: (b"clean-photo", "image/jpeg"))
    image_path = f"/api/v1/notifications/{notice['id']}/photos/{notice['photo_ids'][0]}"
    assert client.get(image_path).status_code == 401
    assert client.get(image_path, headers=auth_headers).content == b"clean-photo"
    assert client.get(f"/api/v1/notifications/{notice['id']}/photos/{uuid4()}", headers=auth_headers).status_code == 404


def test_bad_uploads_are_rejected_and_failed_analysis_is_reported_as_unverified(client, auth_headers, db_factory, monkeypatch):
    _, case = lost_notice(client, auth_headers)
    assert submit(client, case, files=[("photos", ("x.svg", b"svg", "image/svg+xml"))]).status_code == 415
    assert submit(client, case, files=[("photos", ("x.jpg", b"photo", "image/jpeg"))] * 6).status_code == 422
    monkeypatch.setattr(settings, "max_photo_size_bytes", 3)
    assert submit(client, case, files=[("photos", ("x.jpg", b"too-large", "image/jpeg"))]).status_code == 413
    monkeypatch.setattr(settings, "max_photo_size_bytes", 10 * 1024 * 1024)
    mock_storage(monkeypatch)
    monkeypatch.setattr(settings, "ai_enabled", True)
    response = submit(client, case, files=[("photos", ("x.jpg", b"photo", "image/jpeg"))])
    with db_factory() as db:
        job = db.scalar(select(AnalysisJob).where(AnalysisJob.owner_id == UUID(response.json()["id"])))
        job.status = "FAILED"
        assert linked.evaluate_sighting(db, UUID(response.json()["id"])) == "UNVERIFIED"
        db.commit()
    notice = client.get("/api/v1/notifications", headers=auth_headers).json()["items"][0]
    assert notice["kind"] == "REPORTED_SIGHTING"
    assert "por confirmar" in notice["body"]


def test_worker_completion_triggers_matching_without_a_browser(client, auth_headers, db_factory, monkeypatch):
    from tests.test_analysis import FakeProvider
    _, case = lost_notice(client, auth_headers)
    mock_storage(monkeypatch)
    monkeypatch.setattr(settings, "ai_enabled", True)
    response = submit(client, case, files=[("photos", ("x.jpg", b"photo", "image/jpeg"))])
    with db_factory() as db:
        job = db.scalar(select(AnalysisJob).where(AnalysisJob.owner_id == UUID(response.json()["id"])))
        job_id = job.id
    monkeypatch.setattr(tasks, "SessionLocal", db_factory)
    monkeypatch.setattr(tasks, "get_provider", lambda *_: FakeProvider())
    from io import BytesIO
    from PIL import Image
    image=BytesIO()
    Image.new("RGB",(50,50),"brown").save(image,format="JPEG")
    monkeypatch.setattr(tasks, "load_analysis_image", lambda *_: (image.getvalue(), "image/jpeg"))
    assert tasks.process_analysis(str(job_id), 0) == "SUCCEEDED"
    assert client.get("/api/v1/notifications", headers=auth_headers).json()["total"] == 1


def test_deleting_a_case_cleans_notifications_without_deleting_the_sighting(client, auth_headers, db_factory):
    _, case = lost_notice(client, auth_headers)
    response = submit(client, case)
    assert client.delete(f"/api/v1/lost-cases/{case['id']}", headers=auth_headers).status_code == 204
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Notification)) == 0
        assert db.get(Observation, UUID(response.json()["id"])).linked_case_id is None


def test_email_outbox_retries_and_sends_each_notification_once(client, auth_headers, db_factory, monkeypatch):
    _, case = lost_notice(client, auth_headers)
    submit(client, case)
    monkeypatch.setattr(settings, "mail_delivery_mode", "smtp")
    messages = []
    def temporary_failure(message):
        raise OSError("temporary SMTP failure")
    monkeypatch.setattr(email, "send_message", temporary_failure)
    assert email.deliver_pending(db_factory) == 0
    with db_factory() as db:
        notification = db.scalar(select(Notification))
        assert notification.email_status == "PENDING"
        assert notification.email_attempts == 1
        notification.email_available_at = utcnow() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(email, "send_message", lambda message: messages.append(message))
    assert email.deliver_pending(db_factory) == 1
    assert email.deliver_pending(db_factory) == 0
    assert len(messages) == 1
    assert messages[0]["To"] == "owner@example.com"
    assert "/notificaciones?aviso=" in messages[0].get_content()
    assert "-34.90123" not in messages[0].get_content()


def test_email_preference_and_inactive_notice_prevent_sends(client, auth_headers, db_factory, monkeypatch):
    _, case = lost_notice(client, auth_headers)
    submit(client, case)
    assert client.patch("/api/v1/auth/notification-preferences", headers=auth_headers, json={"email": False}).status_code == 200
    monkeypatch.setattr(settings, "mail_delivery_mode", "smtp")
    monkeypatch.setattr(email, "send_message", lambda _: pytest.fail("Email should not be sent"))
    assert email.deliver_pending(db_factory) == 0
    with db_factory() as db:
        assert db.scalar(select(Notification)).email_status == "SKIPPED"


def test_real_smtp_requires_tls_and_preview_cannot_use_an_external_host():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mail_delivery_mode="smtp", smtp_tls_mode="none")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mail_delivery_mode="preview", smtp_host="smtp-relay.brevo.com")
    settings_object = Settings(_env_file=None, smtp_password="secret")
    assert "secret" not in str(settings_object.smtp_password)
