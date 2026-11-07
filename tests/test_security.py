"""T22 — Authentication, authorisation, CSRF and response hardening."""
from app.constants import Roles
from app.extensions import db
from app.models.audit_log import AuditLog

from .factories import TEST_PASSWORD, make_user


def _login(app, email, password=TEST_PASSWORD):
    client = app.test_client()
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302, response.data[:400]
    return client


def test_passwords_are_stored_as_hashes(app, base):
    assert base.patient.password_hash != TEST_PASSWORD
    assert base.patient.password_hash.startswith(("pbkdf2:", "scrypt:"))
    assert base.patient.check_password(TEST_PASSWORD)


def test_login_rejects_sql_injection_payload(client, app, base):
    response = client.post(
        "/login",
        data={"email": base.admin.email, "password": "' OR '1'='1' --"},
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data

    guarded = client.get("/patient/dashboard")
    assert guarded.status_code == 302
    assert "/login" in guarded.headers["Location"]
    assert AuditLog.query.filter_by(action="login_failed").count() == 1


def test_missing_csrf_token_is_rejected(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    response = client.post(
        "/login", data={"email": "someone@test.local", "password": "Secret123"}
    )
    assert response.status_code == 400
    assert b"Session expired" in response.data or b"400" in response.data


def test_csrf_failure_returns_json_for_api_clients(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    response = client.post(
        "/login",
        data={"email": "someone@test.local", "password": "Secret123"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "CSRF_ERROR"


def test_security_headers_are_added_to_every_response(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in response.headers["Permissions-Policy"]


def test_session_cookie_is_http_only_and_same_site(app, base):
    client = app.test_client()
    response = client.post(
        "/login", data={"email": base.patient.email, "password": TEST_PASSWORD}
    )
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()


def test_patient_cannot_reach_admin_or_doctor_areas(app, base):
    patient = _login(app, base.patient.email)

    assert patient.get("/admin/dashboard").status_code == 403
    assert patient.get("/admin/api/stats").status_code == 403
    assert patient.get("/doctor/dashboard").status_code == 403
    assert patient.get("/doctor/schedule").status_code == 403


def test_doctor_cannot_reach_admin_area(app, base):
    doctor = _login(app, base.doctor.user.email)
    assert doctor.get("/admin/dashboard").status_code == 403
    assert doctor.get("/admin/patients").status_code == 403


def test_admin_cannot_enter_the_patient_portal(app, base):
    admin = _login(app, base.admin.email)
    assert admin.get("/patient/dashboard").status_code == 403
    assert admin.get("/patient/appointments").status_code == 403


def test_api_role_violation_returns_json(app, base):
    patient = _login(app, base.patient.email)
    response = patient.get("/admin/api/stats")
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "FORBIDDEN"


def test_disabled_account_loses_access_immediately(app, base):
    client = _login(app, base.patient.email)

    base.patient.is_active = False
    db.session.commit()

    response = client.get("/patient/dashboard")
    assert response.status_code == 403


def test_anonymous_protected_routes_redirect_to_login(app, base):
    anonymous = app.test_client()
    for path in (
        "/patient/dashboard",
        "/patient/appointments",
        "/doctor/dashboard",
        "/admin/dashboard",
    ):
        response = anonymous.get(path)
        assert response.status_code == 302, path
        assert "/login" in response.headers["Location"], path


def test_inactive_users_cannot_authenticate(client, app, base):
    blocked = make_user("Blocked User", "blocked@test.local", is_active=False)
    db.session.commit()

    response = client.post(
        "/login", data={"email": blocked.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    assert b"disabled" in response.data.lower()


def test_booking_actions_require_a_patient_role(app, base):
    admin = _login(app, base.admin.email)
    response = admin.post("/patient/appointments/MQ-0000/cancel", data={"reason": "x"})
    assert response.status_code == 403


def test_audit_log_records_privileged_actions(app, base):
    admin = _login(app, base.admin.email)
    response = admin.post(f"/admin/patients/{base.patient.id}/toggle")
    assert response.status_code == 302

    entry = AuditLog.query.filter_by(action="patient_toggled").first()
    assert entry is not None
    assert entry.actor_user_id == base.admin.id
    assert entry.entity_type == "user"
    assert entry.entity_id == base.patient.id
