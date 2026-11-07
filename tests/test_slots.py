"""T05 — Date and slot selection."""
from datetime import date, datetime, time, timedelta

from app.constants import SlotStatus
from app.extensions import db
from app.services import slot_service

from .factories import TEST_PASSWORD, future_day, make_schedule, make_slot


def _login(client, email):
    client.post("/login", data={"email": email, "password": TEST_PASSWORD})


def test_slot_api_returns_available_slots(client, app, base):
    day = future_day()
    slot = make_slot(base.doctor, day=day, start=time(10, 0))
    db.session.commit()

    response = client.get(f"/api/doctors/{base.doctor.id}/slots?date={day.isoformat()}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["is_working_day"] is True
    assert payload["summary"]["available"] == 1
    row = next(item for item in payload["slots"] if item["id"] == slot.id)
    assert row["start"] == "10:00"
    assert row["available"] is True
    assert row["status"] == SlotStatus.AVAILABLE


def test_slot_api_rejects_past_dates(client, app, base):
    yesterday = date.today() - timedelta(days=1)
    response = client.get(
        f"/api/doctors/{base.doctor.id}/slots?date={yesterday.isoformat()}"
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "DATE_OUT_OF_RANGE"


def test_slot_api_rejects_dates_beyond_booking_window(client, app, base):
    far = date.today() + timedelta(days=60)
    response = client.get(
        f"/api/doctors/{base.doctor.id}/slots?date={far.isoformat()}"
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "DATE_OUT_OF_RANGE"


def test_slot_api_404_for_unknown_doctor(client, app, base):
    response = client.get("/api/doctors/999999/slots")
    assert response.status_code == 404
    assert response.get_json()["ok"] is False


def test_next_available_endpoint(client, app, base):
    day = future_day(3)
    make_slot(base.doctor, day=day, start=time(9, 30))
    db.session.commit()

    response = client.get(
        f"/api/doctors/{base.doctor.id}/next-available?from={future_day(2).isoformat()}"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["available"] is True
    assert payload["slot"]["date"] == day.isoformat()
    assert payload["slot"]["start"] == "09:30"


def test_next_available_reports_none_for_full_doctor(client, app, base):
    response = client.get(
        f"/api/doctors/{base.other_doctor.id}/next-available?from={future_day(40).isoformat()}"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["available"] is False
    assert payload["slot"] is None


def test_serialization_marks_past_slots_closed(app, base):
    yesterday = date.today() - timedelta(days=1)
    make_slot(base.doctor, day=yesterday, start=time(10, 0))
    db.session.commit()

    payload = slot_service.serialize_slots(base.doctor.id, yesterday)
    assert payload["slots"][0]["status"] == SlotStatus.CLOSED
    assert payload["slots"][0]["available"] is False


def test_booking_page_lists_dates_and_slots(client, app, base):
    day = future_day()
    make_schedule(
        base.doctor,
        weekday=day.weekday(),
        start=time(10, 0),
        end=time(11, 0),
        duration=20,
    )
    make_slot(base.doctor, day=day, start=time(10, 0))
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get(f"/patient/book/{base.doctor.id}?date={day.isoformat()}")
    assert response.status_code == 200
    assert b"Arjun Mehta" in response.data
    assert b"10:00 AM" in response.data
    assert b"No open dates" not in response.data


def test_booking_page_renders_without_slots(client, app, base):
    _login(client, base.patient.email)
    response = client.get(f"/patient/book/{base.other_doctor.id}")
    assert response.status_code == 200
    assert b"No open dates" in response.data


def test_claim_slot_is_atomic_and_reversible(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(14, 0))
    db.session.commit()

    assert slot_service.claim_slot(slot.id) is True
    assert slot_service.claim_slot(slot.id) is False

    db.session.expire_all()
    assert db.session.get(type(slot), slot.id).status == SlotStatus.BOOKED
    assert slot_service.release_slot(slot.id) is True
    db.session.expire_all()
    assert db.session.get(type(slot), slot.id).status == SlotStatus.AVAILABLE
