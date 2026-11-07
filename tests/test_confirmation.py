"""T07 — Booking confirmation page and email content."""
from datetime import time

from app.extensions import db
from app.models.appointment import Appointment
from app.models.notification import Notification

from .factories import TEST_PASSWORD, future_day, make_slot


def _book(app, email, doctor, slot):
    client = app.test_client()
    client.post("/login", data={"email": email, "password": TEST_PASSWORD})
    response = client.post(
        f"/patient/book/{doctor.id}",
        data={"slot_id": slot.id, "reason": "Follow-up"},
    )
    assert response.status_code == 302
    return client


def test_confirmation_page_shows_all_visit_details(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(10, 0))
    db.session.commit()

    client = _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()

    response = client.get(f"/patient/confirmation/{appointment.booking_id}")
    assert response.status_code == 200
    body = response.data
    assert appointment.booking_id.encode() in body
    assert b"Arjun Mehta" in body
    assert b"Cardiology" in body
    assert b"C-204" in body
    assert b"500" in body  # fee
    assert b"Booking ID" in body
    assert b"No wait" in body


def test_confirmation_is_private_to_the_patient(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(11, 0))
    db.session.commit()

    _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()

    other = app.test_client()
    other.post(
        "/login", data={"email": base.other_patient.email, "password": TEST_PASSWORD}
    )
    response = other.get(f"/patient/confirmation/{appointment.booking_id}")
    assert response.status_code == 403


def test_unknown_booking_id_is_404(app, base):
    client = app.test_client()
    client.post(
        "/login", data={"email": base.patient.email, "password": TEST_PASSWORD}
    )
    response = client.get("/patient/confirmation/MQ-19700101-0001")
    assert response.status_code == 404


def test_booking_sends_confirmation_notification(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(12, 0))
    db.session.commit()

    _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()

    notification = Notification.query.filter_by(
        appointment_id=appointment.id, type="booking_confirmation"
    ).one()
    assert notification.recipient_email == base.patient.email
    assert notification.status == "sent"
    assert appointment.booking_id in notification.subject
    assert appointment.booking_id in (notification.body or "")
    assert "Arjun Mehta" in (notification.body or "")
