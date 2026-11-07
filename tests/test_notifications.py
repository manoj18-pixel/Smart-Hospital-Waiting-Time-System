"""T13 — Email notification logging and delivery-failure handling."""
from datetime import time

from app.constants import AppointmentStatus, SlotStatus
from app.extensions import db, mail
from app.models.appointment import Appointment
from app.models.notification import Notification
from app.models.slot import Slot
from app.services import mail_service

from .factories import TEST_PASSWORD, future_day, make_appointment, make_slot


def _login(app, email):
    client = app.test_client()
    response = client.post("/login", data={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 302
    return client


def _book(app, email, doctor, slot, reason="Persistent cough"):
    client = _login(app, email)
    response = client.post(
        f"/patient/book/{doctor.id}",
        data={"slot_id": slot.id, "reason": reason},
    )
    assert response.status_code == 302
    return client


def test_confirmation_email_is_rendered_and_logged(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(10, 0))
    db.session.commit()

    _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()
    notification = Notification.query.filter_by(
        appointment_id=appointment.id, type="booking_confirmation"
    ).one()

    assert notification.channel == "email"
    assert notification.user_id == base.patient.id
    assert notification.recipient_email == base.patient.email
    assert notification.status == "sent"
    assert notification.sent_at is not None
    assert notification.error_message is None
    assert notification.subject == f"Appointment confirmed - {appointment.booking_id}"
    assert appointment.booking_id in notification.body
    assert "Arjun Mehta" in notification.body
    assert "Interventional Cardiologist" in notification.body
    assert "Cardiology" in notification.body
    assert "C-204" in notification.body


def test_cancellation_email_is_rendered_and_logged(app, base):
    slot = make_slot(base.doctor, day=future_day(4), start=time(11, 0))
    db.session.commit()

    client = _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()
    response = client.post(
        f"/patient/appointments/{appointment.booking_id}/cancel",
        data={"reason": "Recovered already"},
    )
    assert response.status_code == 302

    notification = Notification.query.filter_by(
        appointment_id=appointment.id, type="cancellation"
    ).one()
    assert notification.status == "sent"
    assert notification.subject == f"Appointment cancelled - {appointment.booking_id}"
    assert "Appointment cancelled" in notification.body
    assert "at your request" in notification.body
    assert "Recovered already" in notification.body
    assert "released" in notification.body


def test_hospital_initiated_cancellation_is_worded_correctly(app, base):
    slot = make_slot(
        base.doctor, day=future_day(4), start=time(12, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(base.patient, slot)
    db.session.commit()

    mail_service.send_cancellation(appointment, cancelled_by="hospital")
    notification = Notification.query.filter_by(
        appointment_id=appointment.id, type="cancellation"
    ).one()
    assert "by the hospital" in notification.body
    assert "at your request" not in notification.body


def test_delivery_failure_marks_notification_failed_but_keeps_booking(
    app, base, monkeypatch
):
    def broken_send(message):  # pragma: no cover - exercised through service
        raise RuntimeError("SMTP server unreachable")

    monkeypatch.setattr(mail, "send", broken_send)

    slot = make_slot(base.doctor, day=future_day(), start=time(13, 0))
    db.session.commit()
    slot_id = slot.id

    _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()
    notification = Notification.query.filter_by(
        appointment_id=appointment.id, type="booking_confirmation"
    ).one()

    assert appointment.status == AppointmentStatus.CONFIRMED
    assert notification.status == "failed"
    assert notification.sent_at is None
    assert "SMTP server unreachable" in notification.error_message

    db.session.expire_all()
    assert db.session.get(Slot, slot_id).status == SlotStatus.BOOKED


def test_each_booking_creates_exactly_one_notification(app, base):
    slot_one = make_slot(base.doctor, day=future_day(2), start=time(9, 0))
    slot_two = make_slot(base.other_doctor, day=future_day(3), start=time(9, 0))
    db.session.commit()

    client = _book(app, base.patient.email, base.doctor, slot_one)
    assert client.post(
        f"/patient/book/{base.other_doctor.id}",
        data={"slot_id": slot_two.id, "reason": "Second opinion"},
    ).status_code == 302

    assert Appointment.query.count() == 2
    assert Notification.query.filter_by(type="booking_confirmation").count() == 2
    assert Notification.query.filter_by(status="failed").count() == 0
