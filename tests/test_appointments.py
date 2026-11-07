"""T12 — Appointment listing scopes and detail pages."""
from datetime import date, datetime, time, timedelta

from app.constants import AppointmentStatus, SlotStatus
from app.extensions import db

from .factories import TEST_PASSWORD, future_day, make_appointment, make_slot


def _login(client, email):
    client.post("/login", data={"email": email, "password": TEST_PASSWORD})


def _appointment(patient, doctor, day, start, status, sequence):
    slot = make_slot(doctor, day=day, start=start, status=SlotStatus.BOOKED)
    appointment = make_appointment(
        patient, slot, status=status, booking_id=f"MQ-{sequence:04d}"
    )
    if status == AppointmentStatus.CANCELLED:
        appointment.cancelled_at = datetime.utcnow()
        appointment.cancel_reason = "Test cancellation"
    return appointment


def test_appointment_scopes_filter_correctly(client, app, base):
    upcoming = _appointment(
        base.patient, base.doctor, future_day(2), time(9, 0), AppointmentStatus.CONFIRMED, 101
    )
    completed = _appointment(
        base.patient, base.doctor, future_day(3), time(9, 0), AppointmentStatus.COMPLETED, 102
    )
    cancelled = _appointment(
        base.patient, base.doctor, future_day(4), time(9, 0), AppointmentStatus.CANCELLED, 103
    )
    no_show = _appointment(
        base.patient, base.doctor, future_day(5), time(9, 0), AppointmentStatus.NO_SHOW, 104
    )
    past = _appointment(
        base.patient,
        base.doctor,
        date.today() - timedelta(days=2),
        time(9, 0),
        AppointmentStatus.CONFIRMED,
        105,
    )
    db.session.commit()

    _login(client, base.patient.email)

    response = client.get("/patient/appointments?scope=upcoming")
    assert response.status_code == 200
    assert upcoming.booking_id.encode() in response.data
    assert completed.booking_id.encode() not in response.data
    assert past.booking_id.encode() not in response.data

    response = client.get("/patient/appointments?scope=past")
    assert completed.booking_id.encode() in response.data
    assert no_show.booking_id.encode() in response.data
    assert past.booking_id.encode() in response.data
    assert upcoming.booking_id.encode() not in response.data

    response = client.get("/patient/appointments?scope=cancelled")
    assert cancelled.booking_id.encode() in response.data
    assert upcoming.booking_id.encode() not in response.data

    response = client.get("/patient/appointments?scope=all")
    for appointment in (upcoming, completed, cancelled, no_show, past):
        assert appointment.booking_id.encode() in response.data


def test_appointments_are_scoped_to_the_logged_in_patient(client, app, base):
    mine = _appointment(
        base.patient, base.doctor, future_day(2), time(10, 0), AppointmentStatus.CONFIRMED, 111
    )
    theirs = _appointment(
        base.other_patient,
        base.doctor,
        future_day(2),
        time(10, 30),
        AppointmentStatus.CONFIRMED,
        112,
    )
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get("/patient/appointments?scope=all")
    assert mine.booking_id.encode() in response.data
    assert theirs.booking_id.encode() not in response.data


def test_appointment_detail_page(client, app, base):
    appointment = _appointment(
        base.patient, base.doctor, future_day(2), time(11, 0), AppointmentStatus.CONFIRMED, 121
    )
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get(f"/patient/appointments/{appointment.booking_id}")
    assert response.status_code == 200
    assert appointment.booking_id.encode() in response.data
    assert b"Arjun Mehta" in response.data
    assert b"Cancellable" in response.data or b"Cancel appointment" in response.data


def test_appointment_detail_is_private(client, app, base):
    appointment = _appointment(
        base.patient, base.doctor, future_day(2), time(12, 0), AppointmentStatus.CONFIRMED, 131
    )
    db.session.commit()

    _login(client, base.other_patient.email)
    response = client.get(f"/patient/appointments/{appointment.booking_id}")
    assert response.status_code == 403


def test_unknown_appointment_detail_is_404(client, app, base):
    _login(client, base.patient.email)
    response = client.get("/patient/appointments/MQ-19700101-9999")
    assert response.status_code == 404


def test_dashboard_shows_upcoming_and_stats(client, app, base):
    _appointment(
        base.patient, base.doctor, future_day(2), time(9, 30), AppointmentStatus.CONFIRMED, 141
    )
    completed = _appointment(
        base.patient, base.doctor, future_day(3), time(9, 30), AppointmentStatus.COMPLETED, 142
    )
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get("/patient/dashboard")
    assert response.status_code == 200
    assert b"Asha Verma" in response.data
    assert b"Arjun Mehta" in response.data
    assert b"Upcoming appointments" in response.data or b"Upcoming" in response.data
