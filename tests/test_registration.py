"""T01 — Patient registration."""
from app.constants import Roles
from app.extensions import db
from app.models.user import User

from .factories import make_user


def _payload(**overrides):
    data = {
        "full_name": "New Patient",
        "email": "new.patient@example.test",
        "phone": "+91 90000 00000",
        "password": "Strong123",
        "confirm_password": "Strong123",
        "accept_terms": "y",
    }
    data.update(overrides)
    return data


def test_valid_registration_creates_hashed_patient(client, app):
    response = client.post("/register", data=_payload())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    user = User.query.filter_by(email="new.patient@example.test").first()
    assert user is not None
    assert user.role == Roles.PATIENT
    assert user.patient_profile is not None
    assert user.password_hash != "Strong123"
    assert user.check_password("Strong123")


def test_duplicate_email_is_rejected(client, app):
    make_user("Existing Patient", "taken@example.test")
    db.session.commit()

    response = client.post("/register", data=_payload(email="taken@example.test"))
    assert response.status_code == 200
    assert b"already exists" in response.data


def test_weak_password_is_rejected(client, app):
    response = client.post(
        "/register",
        data=_payload(password="short", confirm_password="short"),
    )
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data
    assert User.query.filter_by(email="new.patient@example.test").first() is None


def test_password_mismatch_is_rejected(client, app):
    response = client.post(
        "/register",
        data=_payload(confirm_password="Different123"),
    )
    assert response.status_code == 200
    assert b"Passwords must match" in response.data


def test_terms_must_be_accepted(client, app):
    data = _payload()
    data.pop("accept_terms")
    response = client.post("/register", data=data)
    assert response.status_code == 200
    assert User.query.filter_by(email="new.patient@example.test").first() is None


def test_authenticated_user_is_redirected_from_register(client, app, base):
    client.post(
        "/login",
        data={"email": base.patient.email, "password": "Secret123"},
    )
    response = client.get("/register")
    assert response.status_code == 302
    assert "/patient/dashboard" in response.headers["Location"]
