"""T14 — Doctor daily schedule and queue transitions."""
from datetime import date, time

from app.constants import AppointmentStatus, SlotStatus
from app.extensions import db
from app.models.appointment import Appointment
from app.services import waiting_service

from .factories import TEST_PASSWORD, make_appointment, make_slot, make_user


def _login(app, email, password=TEST_PASSWORD):
    client = app.test_client()
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302
    return client


def _today_appointment(doctor, patient, clock, status=AppointmentStatus.CONFIRMED, booking_id=None):
    slot = make_slot(doctor, day=date.today(), start=clock, status=SlotStatus.BOOKED)
    return make_appointment(patient, slot, status=status, booking_id=booking_id)


def test_doctor_sees_only_their_own_patients(app, base):
    own_one = _today_appointment(base.doctor, base.patient, time(9, 0), booking_id="MQ-OWN-1")
    own_two = _today_appointment(base.doctor, base.other_patient, time(10, 0), booking_id="MQ-OWN-2")
    third = make_user("Zoya Khan", "zoya@test.local")
    other = _today_appointment(
        base.other_doctor, third, time(9, 30), booking_id="MQ-OTHER-1"
    )
    db.session.commit()

    client = _login(app, base.doctor.user.email)
    response = client.get(f"/doctor/schedule?date={date.today().isoformat()}")
    assert response.status_code == 200
    body = response.data
    assert b"Asha Verma" in body
    assert b"Ravi Kumar" in body
    assert b"Zoya Khan" not in body
    assert b"MQ-OWN-1" in body
    assert b"MQ-OTHER-1" not in body
    assert body.index(b"Asha Verma") < body.index(b"Ravi Kumar")


def test_doctor_dashboard_renders_queue(app, base):
    _today_appointment(base.doctor, base.patient, time(9, 0))
    db.session.commit()

    client = _login(app, base.doctor.user.email)
    response = client.get("/doctor/dashboard")
    assert response.status_code == 200
    assert b"Asha Verma" in response.data
    assert b"Today's queue" in response.data


def test_check_in_then_complete_consultation(app, base):
    appointment = _today_appointment(base.doctor, base.patient, time(9, 0))
    db.session.commit()

    client = _login(app, base.doctor.user.email)
    response = client.post(f"/doctor/appointments/{appointment.id}/checkin")
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(Appointment, appointment.id).status == AppointmentStatus.CHECKED_IN
    assert db.session.get(Appointment, appointment.id).checked_in_at is not None

    response = client.post(f"/doctor/appointments/{appointment.id}/complete")
    assert response.status_code == 302
    db.session.expire_all()
    updated = db.session.get(Appointment, appointment.id)
    assert updated.status == AppointmentStatus.COMPLETED
    assert updated.completed_at is not None


def test_mark_no_show(app, base):
    appointment = _today_appointment(base.doctor, base.patient, time(9, 0))
    db.session.commit()

    client = _login(app, base.doctor.user.email)
    response = client.post(f"/doctor/appointments/{appointment.id}/no-show")
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(Appointment, appointment.id).status == AppointmentStatus.NO_SHOW


def test_doctor_cannot_manage_another_doctors_appointment(app, base):
    appointment = _today_appointment(base.other_doctor, base.patient, time(9, 0))
    db.session.commit()

    client = _login(app, base.doctor.user.email)
    response = client.post(f"/doctor/appointments/{appointment.id}/checkin")
    assert response.status_code == 403
    db.session.expire_all()
    assert db.session.get(Appointment, appointment.id).status == AppointmentStatus.CONFIRMED


def test_doctor_updates_running_delay(app, base):
    today = date.today()
    client = _login(app, base.doctor.user.email)
    response = client.post(
        "/doctor/delay",
        data={"delay_minutes": "12", "date": today.isoformat()},
    )
    assert response.status_code == 302
    assert waiting_service.delay_minutes(base.doctor.id, today) == 12

    # Simulate request teardown: the next request gets a fresh session. Without
    # an explicit commit the delay would disappear here.
    db.session.remove()
    assert waiting_service.delay_minutes(base.doctor.id, today) == 12


def test_delay_validation_rejects_out_of_range(app, base):
    client = _login(app, base.doctor.user.email)
    response = client.post(
        "/doctor/delay",
        data={"delay_minutes": "999", "date": date.today().isoformat()},
    )
    assert response.status_code == 302
    assert waiting_service.delay_minutes(base.doctor.id, date.today()) == 0


def test_patient_cannot_access_doctor_area(app, base):
    client = _login(app, base.patient.email)
    assert client.get("/doctor/dashboard").status_code == 403
    assert client.get("/doctor/schedule").status_code == 403
