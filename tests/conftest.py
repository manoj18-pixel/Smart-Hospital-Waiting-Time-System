"""Shared pytest fixtures for MediQueue.

Tests run against a temporary file-backed SQLite database so the concurrency
test can use independent connections (in-memory SQLite databases are private to
each connection). CSRF and rate limiting are disabled, mail is suppressed.
"""
import os
from types import SimpleNamespace

import pytest
from flask import g

from app import create_app
from app.constants import Roles
from app.extensions import db

from .factories import (
    TEST_PASSWORD,
    make_department,
    make_doctor,
    make_user,
)


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "mediqueue-test.db"
    application = create_app(
        "testing",
        overrides={
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
            "TESTING": True,
            "DEBUG": False,
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
            "MAIL_SUPPRESS_SEND": True,
            "SERVER_NAME": None,
        },
    )
    # The app context stays open for the whole test so tests can query models
    # directly. Flask reuses that context for test-client requests, which means
    # Flask-Login's ``g._login_user`` cache would otherwise leak the previous
    # request's user into the next one. Clear it so every request reloads the
    # user from that client's own session cookie.
    @application.before_request
    def _reload_login_user_per_request():
        g.pop("_login_user", None)

    with application.app_context():
        db.create_all()
        try:
            yield application
        finally:
            db.session.remove()
            db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def base(app):
    """A small hospital: two departments, two doctors, two patients, an admin."""
    department = make_department("Cardiology")
    doctor = make_doctor(
        department,
        full_name="Arjun Mehta",
        email="dr.arjun@test.local",
        specialization="Interventional Cardiologist",
        avg_consult_minutes=15,
        consultation_fee=500,
    )
    other_department = make_department("Neurology")
    other_doctor = make_doctor(
        other_department,
        full_name="Kavya Rao",
        email="dr.kavya@test.local",
        specialization="Neurologist",
        avg_consult_minutes=20,
        consultation_fee=700,
    )
    patient = make_user("Asha Verma", "asha@test.local")
    other_patient = make_user("Ravi Kumar", "ravi@test.local")
    admin = make_user("Hospital Admin", "admin@test.local", role=Roles.ADMIN)
    db.session.commit()
    return SimpleNamespace(
        department=department,
        doctor=doctor,
        other_department=other_department,
        other_doctor=other_doctor,
        patient=patient,
        other_patient=other_patient,
        admin=admin,
    )


@pytest.fixture()
def login(client):
    """Return a helper that signs a client in and returns the response."""

    def _login(email, password=TEST_PASSWORD, follow_redirects=False):
        return client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=follow_redirects,
        )

    return _login


@pytest.fixture()
def auth_client(app):
    """Factory: return a freshly logged-in test client for an email."""

    def _make(email, password=TEST_PASSWORD):
        client = app.test_client()
        response = client.post(
            "/login", data={"email": email, "password": password}
        )
        assert response.status_code == 302, response.data[:500]
        return client

    return _make


@pytest.fixture(autouse=True)
def _quiet_mail(monkeypatch):
    """Never talk to a real SMTP server, even if config is overridden."""
    monkeypatch.setenv("MAIL_SUPPRESS_SEND", "true")
    yield
