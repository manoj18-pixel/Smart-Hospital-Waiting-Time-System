"""T02 — Login, logout and session handling."""
from app.extensions import db
from app.models.audit_log import AuditLog

from .factories import TEST_PASSWORD


def test_login_success_redirects_to_patient_dashboard(client, app, base):
    response = client.post(
        "/login", data={"email": base.patient.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/patient/dashboard")

    response = client.get("/patient/dashboard")
    assert response.status_code == 200
    assert base.patient.full_name.encode() in response.data


def test_login_is_case_insensitive_on_email(client, app, base):
    response = client.post(
        "/login",
        data={"email": base.patient.email.upper(), "password": TEST_PASSWORD},
    )
    assert response.status_code == 302
    assert "/patient/dashboard" in response.headers["Location"]


def test_wrong_password_is_rejected(client, app, base):
    response = client.post(
        "/login", data={"email": base.patient.email, "password": "WrongPass123"}
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data
    assert AuditLog.query.filter_by(action="login_failed").count() == 1


def test_disabled_account_cannot_sign_in(client, app, base):
    base.patient.is_active = False
    db.session.commit()

    response = client.post(
        "/login", data={"email": base.patient.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    assert b"disabled" in response.data.lower()


def test_logout_ends_the_session(client, app, base):
    client.post(
        "/login", data={"email": base.patient.email, "password": TEST_PASSWORD}
    )
    response = client.post("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    protected = client.get("/patient/dashboard")
    assert protected.status_code == 302
    assert "/login" in protected.headers["Location"]


def test_safe_next_redirect_is_honoured(client, app, base):
    response = client.post(
        "/login?next=/patient/appointments",
        data={"email": base.patient.email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/patient/appointments")


def test_external_next_redirect_is_ignored(client, app, base):
    response = client.post(
        "/login?next=//evil.example.com/steal",
        data={"email": base.patient.email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/patient/dashboard")


def test_authenticated_user_is_redirected_away_from_login(client, app, base):
    client.post(
        "/login", data={"email": base.patient.email, "password": TEST_PASSWORD}
    )
    response = client.get("/login")
    assert response.status_code == 302
    assert "/patient/dashboard" in response.headers["Location"]


def test_login_records_successful_audit_entry(client, app, base):
    client.post(
        "/login", data={"email": base.patient.email, "password": TEST_PASSWORD}
    )
    entry = AuditLog.query.filter_by(action="login").first()
    assert entry is not None
    assert entry.actor_user_id == base.patient.id
