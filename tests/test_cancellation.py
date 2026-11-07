"""T10 & T11 — Cancellation, slot release and cancellation rules."""
from datetime import datetime, time, timedelta

from app.constants import AppointmentStatus, SlotStatus
from app.extensions import db
from app.models.appointment import Appointment
from app.models.notification import Notification
from app.models.setting import Setting
from app.models.slot import Slot
from app.services import booking_service

from .factories import TEST_PASSWORD, future_day, make_appointment, make_slot


def _login(app, email):
    client = app.test_client()
    client.post("/login", data={"email": email, "password": TEST_PASSWORD})
    return client


def _book(app, email, doctor, slot):
    client = _login(app, email)
    response = client.post(
        f"/patient/book/{doctor.id}",
        data={"slot_id": slot.id, "reason": "Needs review"},
    )
    assert response.status_code == 302
    return client


def test_patient_can_cancel_before_cutoff_and_slot_reopens(app, base):
    slot = make_slot(base.doctor, day=future_day(3), start=time(10, 0))
    db.session.commit()

    client = _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()

    response = client.post(
        f"/patient/appointments/{appointment.booking_id}/cancel",
        data={"reason": "Travel plans changed"},
    )
    assert response.status_code == 302

    db.session.expire_all()
    updated = db.session.get(Appointment, appointment.id)
    assert updated.status == AppointmentStatus.CANCELLED
    assert updated.cancelled_at is not None
    assert updated.cancel_reason == "Travel plans changed"
    assert db.session.get(Slot, slot.id).status == SlotStatus.AVAILABLE


def test_cancellation_writes_notification(app, base):
    slot = make_slot(base.doctor, day=future_day(3), start=time(11, 0))
    db.session.commit()

    client = _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()
    client.post(
        f"/patient/appointments/{appointment.booking_id}/cancel",
        data={"reason": "Feeling better"},
    )

    notification = Notification.query.filter_by(
        appointment_id=appointment.id, type="cancellation"
    ).one()
    assert notification.recipient_email == base.patient.email
    assert appointment.booking_id in notification.subject


def test_cancellation_within_cutoff_is_rejected(app, base):
    start_dt = datetime.now() + timedelta(minutes=45)
    slot = make_slot(base.doctor, day=start_dt.date(), start=start_dt.time())
    db.session.commit()

    client = _book(app, base.patient.email, base.doctor, slot)
    appointment = Appointment.query.one()

    response = client.post(
        f"/patient/appointments/{appointment.booking_id}/cancel",
        data={"reason": "Too late"},
    )
    assert response.status_code == 409
    assert b"2 hours" in response.data

    db.session.expire_all()
    assert db.session.get(Appointment, appointment.id).status == AppointmentStatus.CONFIRMED
    assert db.session.get(Slot, slot.id).status == SlotStatus.BOOKED


def test_cancellation_limit_is_enforced(app, base):
    Setting.set("max_cancellations_per_30_days", "1")
    db.session.commit()

    first_slot = make_slot(base.doctor, day=future_day(4), start=time(10, 0))
    second_slot = make_slot(base.other_doctor, day=future_day(5), start=time(10, 0))
    db.session.commit()

    client = _book(app, base.patient.email, base.doctor, first_slot)
    client.post(
        f"/patient/book/{base.other_doctor.id}",
        data={"slot_id": second_slot.id, "reason": "Second visit"},
    )
    first, second = Appointment.query.order_by(Appointment.id).all()

    response = client.post(
        f"/patient/appointments/{first.booking_id}/cancel",
        data={"reason": "First cancellation"},
    )
    assert response.status_code == 302

    response = client.post(
        f"/patient/appointments/{second.booking_id}/cancel",
        data={"reason": "Second cancellation"},
    )
    assert response.status_code == 409
    assert b"limit" in response.data.lower()

    db.session.expire_all()
    assert db.session.get(Appointment, second.id).status == AppointmentStatus.CONFIRMED


def test_patient_cannot_cancel_another_patients_appointment(app, base):
    slot = make_slot(base.doctor, day=future_day(4), start=time(12, 0), status=SlotStatus.BOOKED)
    appointment = make_appointment(base.patient, slot)
    db.session.commit()

    client = _login(app, base.other_patient.email)
    response = client.post(
        f"/patient/appointments/{appointment.booking_id}/cancel",
        data={"reason": "Not mine"},
    )
    assert response.status_code == 403

    db.session.expire_all()
    assert db.session.get(Appointment, appointment.id).status == AppointmentStatus.CONFIRMED


def test_admin_cancellation_bypasses_cutoff_and_limits(app, base):
    start_dt = datetime.now() + timedelta(minutes=30)
    slot = make_slot(base.doctor, day=start_dt.date(), start=start_dt.time(), status=SlotStatus.BOOKED)
    appointment = make_appointment(base.patient, slot)
    Setting.set("max_cancellations_per_30_days", "0")
    db.session.commit()

    cancelled, released = booking_service.cancel_booking(
        appointment, base.admin, "Hospital emergency", is_admin=True
    )
    assert cancelled.status == AppointmentStatus.CANCELLED
    assert released is True
    assert cancelled.cancel_reason == "Hospital emergency"


def test_cancelled_appointment_cannot_be_cancelled_again(app, base):
    slot = make_slot(base.doctor, day=future_day(4), start=time(13, 0), status=SlotStatus.BOOKED)
    appointment = make_appointment(base.patient, slot)
    db.session.commit()
    booking_service.cancel_booking(appointment, base.patient, "Changed plans")
    db.session.commit()

    try:
        booking_service.cancel_booking(appointment, base.patient, "Again")
    except booking_service.BookingError as exc:
        assert exc.code == "ALREADY_CANCELLED"
        assert exc.status == 409
    else:  # pragma: no cover
        raise AssertionError("second cancellation should fail")


def test_completed_appointment_cannot_be_cancelled(app, base):
    slot = make_slot(base.doctor, day=future_day(4), start=time(14, 0), status=SlotStatus.BOOKED)
    appointment = make_appointment(
        base.patient, slot, status=AppointmentStatus.COMPLETED
    )
    db.session.commit()

    try:
        booking_service.cancel_booking(appointment, base.patient, "Too late")
    except booking_service.BookingError as exc:
        assert exc.code == "NOT_CANCELLABLE"
    else:  # pragma: no cover
        raise AssertionError("completed appointment should not be cancellable")
