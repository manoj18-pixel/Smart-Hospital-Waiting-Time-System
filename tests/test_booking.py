"""T06 & T08 — Successful booking and duplicate prevention."""
import re
from datetime import date, time, timedelta

from app.constants import AppointmentStatus, Roles, SlotStatus
from app.extensions import db
from app.models.appointment import Appointment
from app.models.slot import Slot

from .factories import TEST_PASSWORD, future_day, make_slot, make_user


def _login(app, email, password=TEST_PASSWORD):
    client = app.test_client()
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302
    return client


def _book(client, doctor, slot, reason="Chest pain"):
    return client.post(
        f"/patient/book/{doctor.id}",
        data={
            "slot_id": slot.id,
            "reason": reason,
            "date": slot.slot_date.isoformat(),
        },
    )


def test_successful_booking_locks_the_slot(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(10, 0))
    db.session.commit()

    client = _login(app, base.patient.email)
    response = _book(client, base.doctor, slot)
    assert response.status_code == 302

    appointment = Appointment.query.one()
    assert response.headers["Location"].endswith(
        f"/patient/confirmation/{appointment.booking_id}"
    )
    assert appointment.status == AppointmentStatus.CONFIRMED
    assert appointment.patient_id == base.patient.id
    assert appointment.reason_for_visit == "Chest pain"
    assert re.fullmatch(r"MQ-\d{8}-\d{4}", appointment.booking_id)
    assert appointment.booking_id.startswith(f"MQ-{slot.slot_date:%Y%m%d}")

    db.session.expire_all()
    assert db.session.get(Slot, slot.id).status == SlotStatus.BOOKED


def test_booking_records_queue_estimate(app, base):
    day = future_day()
    earlier = make_slot(base.doctor, day=day, start=time(9, 0))
    later = make_slot(base.doctor, day=day, start=time(10, 0))
    db.session.commit()

    first = _login(app, base.other_patient.email)
    assert _book(first, base.doctor, earlier).status_code == 302

    second = _login(app, base.patient.email)
    assert _book(second, base.doctor, later).status_code == 302

    appointment = Appointment.query.filter_by(patient_id=base.patient.id).one()
    assert appointment.queue_position == 2
    assert appointment.estimated_wait_minutes == base.doctor.avg_consult_minutes


def test_second_patient_gets_409_for_same_slot(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(11, 0))
    db.session.commit()

    first = _login(app, base.patient.email)
    assert _book(first, base.doctor, slot).status_code == 302

    second = _login(app, base.other_patient.email)
    response = _book(second, base.doctor, slot)
    assert response.status_code == 409
    assert b"just booked" in response.data.lower() or b"slot" in response.data.lower()

    assert Appointment.query.count() == 1
    db.session.expire_all()
    assert db.session.get(Slot, slot.id).status == SlotStatus.BOOKED


def test_same_patient_cannot_book_same_doctor_twice_in_a_day(app, base):
    day = future_day()
    first_slot = make_slot(base.doctor, day=day, start=time(10, 0))
    second_slot = make_slot(base.doctor, day=day, start=time(10, 20))
    db.session.commit()

    client = _login(app, base.patient.email)
    assert _book(client, base.doctor, first_slot).status_code == 302

    response = _book(client, base.doctor, second_slot)
    assert response.status_code == 409
    assert b"already have an appointment" in response.data.lower()
    assert Appointment.query.count() == 1
    db.session.expire_all()
    assert db.session.get(Slot, second_slot.id).status == SlotStatus.AVAILABLE


def test_past_slot_cannot_be_booked(app, base):
    yesterday = date.today() - timedelta(days=1)
    slot = make_slot(base.doctor, day=yesterday, start=time(10, 0))
    db.session.commit()

    client = _login(app, base.patient.email)
    response = _book(client, base.doctor, slot)
    assert response.status_code == 302
    assert Appointment.query.count() == 0
    db.session.expire_all()
    # The failed attempt must release its optimistic claim.
    assert db.session.get(Slot, slot.id).status == SlotStatus.AVAILABLE


def test_booking_beyond_open_window_is_rejected(app, base):
    slot = make_slot(base.doctor, day=date.today() + timedelta(days=45), start=time(10, 0))
    db.session.commit()

    client = _login(app, base.patient.email)
    response = _book(client, base.doctor, slot)
    assert response.status_code == 302
    assert Appointment.query.count() == 0
    db.session.expire_all()
    assert db.session.get(Slot, slot.id).status == SlotStatus.AVAILABLE


def test_unknown_slot_returns_404(app, base):
    client = _login(app, base.patient.email)
    response = client.post(
        f"/patient/book/{base.doctor.id}", data={"slot_id": 999999, "reason": "x"}
    )
    assert response.status_code == 302  # flash + redirect for a 404 BookingError
    assert Appointment.query.count() == 0


def test_booking_requires_a_patient_account(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(12, 0))
    db.session.commit()

    anonymous = app.test_client()
    response = anonymous.post(
        f"/patient/book/{base.doctor.id}", data={"slot_id": slot.id}
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    admin = _login(app, base.admin.email)
    assert admin.post(
        f"/patient/book/{base.doctor.id}", data={"slot_id": slot.id}
    ).status_code == 403


def test_inactive_doctor_cannot_be_booked(app, base):
    base.doctor.is_active = False
    db.session.commit()

    client = _login(app, base.patient.email)
    response = client.get(f"/patient/book/{base.doctor.id}")
    assert response.status_code == 404


def test_booking_writes_audit_trail(app, base):
    from app.models.audit_log import AuditLog

    slot = make_slot(base.doctor, day=future_day(), start=time(13, 0))
    db.session.commit()

    client = _login(app, base.patient.email)
    _book(client, base.doctor, slot)

    entry = AuditLog.query.filter_by(action="booking_created").first()
    assert entry is not None
    assert entry.actor_user_id == base.patient.id
