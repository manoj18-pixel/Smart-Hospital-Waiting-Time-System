"""T19 — Friendly HTTP error pages and JSON error envelopes."""
from datetime import time

from flask import abort

from app.constants import SlotStatus
from app.extensions import db
from app.models.appointment import Appointment

from .factories import TEST_PASSWORD, future_day, make_slot


def _login(app, email):
    client = app.test_client()
    response = client.post("/login", data={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 302
    return client


def _abort_view(code):
    def view():
        abort(code)

    return view


def _raise_view():
    raise RuntimeError("deliberate test failure")


def test_unknown_page_renders_html_404(client):
    response = client.get("/definitely-not-a-route")
    assert response.status_code == 404
    assert b"We could not find that page" in response.data
    assert b"404" in response.data


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/definitely-not-a-route")
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_forbidden_page_renders_html_403(app, base):
    patient = _login(app, base.patient.email)
    response = patient.get("/admin/dashboard")
    assert response.status_code == 403
    assert b"You do not have access to this area" in response.data
    assert b"403" in response.data


def test_booking_conflict_renders_html_409(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(10, 0))
    db.session.commit()

    first = _login(app, base.patient.email)
    assert first.post(
        f"/patient/book/{base.doctor.id}",
        data={"slot_id": slot.id, "reason": "First"},
    ).status_code == 302

    second = _login(app, base.other_patient.email)
    response = second.post(
        f"/patient/book/{base.doctor.id}",
        data={"slot_id": slot.id, "reason": "Second"},
    )
    assert response.status_code == 409
    assert b"That slot was just taken" in response.data
    assert b"409" in response.data
    assert Appointment.query.count() == 1


def test_json_409_envelope_is_returned_for_api_paths(app, client):
    app.add_url_rule("/api/__conflict", "__conflict", _abort_view(409))
    response = client.get("/api/__conflict")
    assert response.status_code == 409
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "CONFLICT"


def test_html_and_json_400_responses(app, client):
    app.add_url_rule("/__bad-request", "__bad_request", _abort_view(400))
    app.add_url_rule("/api/__bad-request", "api_bad_request", _abort_view(400))

    html = client.get("/__bad-request")
    assert html.status_code == 400
    assert b"That request could not be processed" in html.data

    payload = client.get("/api/__bad-request").get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "BAD_REQUEST"


def test_html_and_json_500_responses(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.add_url_rule("/__boom", "__boom", _raise_view)
    app.add_url_rule("/api/__boom", "api_boom", _raise_view)

    html = client.get("/__boom")
    assert html.status_code == 500
    assert b"Something went wrong" in html.data

    payload = client.get("/api/__boom").get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "SERVER_ERROR"


def test_health_endpoint_is_public_and_reports_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "mediqueue"


def test_error_pages_are_responsive_html(client):
    response = client.get("/no-such-page")
    assert b'name="viewport"' in response.data
    assert b"bootstrap" in response.data.lower()
