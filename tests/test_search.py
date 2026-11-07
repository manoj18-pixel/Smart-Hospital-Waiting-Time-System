"""T18 — Search, filtering and wait-time API access."""
from datetime import date, datetime, time, timedelta

from app.constants import AppointmentStatus, SlotStatus
from app.extensions import db
from app.models.setting import Setting
from app.services import waiting_service

from .factories import (
    TEST_PASSWORD,
    future_day,
    make_appointment,
    make_slot,
)


def _login(app, email):
    client = app.test_client()
    response = client.post("/login", data={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 302
    return client


def test_admin_patient_search_by_name_is_case_insensitive(app, base):
    admin = _login(app, base.admin.email)

    response = admin.get("/admin/patients", query_string={"q": "ASHA"})
    assert response.status_code == 200
    assert b"Asha Verma" in response.data
    assert b"Ravi Kumar" not in response.data


def test_admin_patient_search_by_partial_email(app, base):
    admin = _login(app, base.admin.email)

    response = admin.get("/admin/patients", query_string={"q": "ravi@"})
    assert response.status_code == 200
    assert b"Ravi Kumar" in response.data
    assert b"Asha Verma" not in response.data


def test_empty_patient_search_lists_everyone(app, base):
    admin = _login(app, base.admin.email)

    response = admin.get("/admin/patients", query_string={"q": "   "})
    assert response.status_code == 200
    assert b"Asha Verma" in response.data
    assert b"Ravi Kumar" in response.data


def test_patient_search_treats_wildcards_as_text(app, base):
    admin = _login(app, base.admin.email)

    response = admin.get(
        "/admin/patients", query_string={"q": "' OR 1=1 --"}
    )
    assert response.status_code == 200
    assert b"Asha Verma" not in response.data
    assert b"Ravi Kumar" not in response.data


def test_appointment_search_by_booking_id_prefix(app, base):
    slot = make_slot(
        base.doctor, day=future_day(2), start=time(9, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(base.patient, slot, booking_id="MQ-20261106-0042")
    db.session.commit()

    admin = _login(app, base.admin.email)
    response = admin.get("/admin/appointments", query_string={"q": "0042"})
    assert response.status_code == 200
    assert appointment.booking_id.encode() in response.data


def test_appointment_filters_combine_status_doctor_and_date(app, base):
    day = future_day(2)
    keep_slot = make_slot(
        base.doctor, day=day, start=time(10, 0), status=SlotStatus.BOOKED
    )
    drop_slot = make_slot(
        base.other_doctor, day=day, start=time(11, 0), status=SlotStatus.BOOKED
    )
    keep = make_appointment(
        base.patient, keep_slot, booking_id="MQ-KEEP-0001"
    )
    drop = make_appointment(
        base.patient,
        drop_slot,
        booking_id="MQ-DROP-0002",
        status=AppointmentStatus.CANCELLED,
    )
    db.session.commit()

    admin = _login(app, base.admin.email)
    response = admin.get(
        "/admin/appointments",
        query_string={
            "date": day.isoformat(),
            "status": AppointmentStatus.CONFIRMED,
            "doctor_id": base.doctor.id,
        },
    )
    assert response.status_code == 200
    assert keep.booking_id.encode() in response.data
    assert drop.booking_id.encode() not in response.data


def test_invalid_appointment_date_filter_is_ignored(app, base):
    slot = make_slot(
        base.doctor, day=future_day(2), start=time(12, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(base.patient, slot, booking_id="MQ-IGNORE-1")
    db.session.commit()

    admin = _login(app, base.admin.email)
    response = admin.get("/admin/appointments", query_string={"date": "not-a-date"})
    assert response.status_code == 200
    assert appointment.booking_id.encode() in response.data


def test_unknown_status_filter_does_not_hide_results(app, base):
    slot = make_slot(
        base.doctor, day=future_day(2), start=time(13, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(base.patient, slot, booking_id="MQ-STATUS-1")
    db.session.commit()

    admin = _login(app, base.admin.email)
    response = admin.get("/admin/appointments", query_string={"status": "NONSENSE"})
    assert response.status_code == 200
    assert appointment.booking_id.encode() in response.data


def test_wait_api_returns_future_estimate_for_owner(app, base):
    slot = make_slot(
        base.doctor, day=future_day(2), start=time(10, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(
        base.patient,
        slot,
        queue_position=3,
        estimated_wait_minutes=30,
        booking_id="MQ-WAIT-0001",
    )
    db.session.commit()

    patient = _login(app, base.patient.email)
    response = patient.get(f"/api/appointments/{appointment.booking_id}/wait")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["booking_id"] == "MQ-WAIT-0001"
    assert payload["queue_position"] == 3
    assert payload["patients_ahead"] == 2
    assert payload["estimated_wait_minutes"] == 30
    assert payload["label"] == "~30 min"
    assert payload["updated_at"]


def test_wait_api_rejects_another_patient(app, base):
    slot = make_slot(
        base.doctor, day=future_day(2), start=time(11, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(base.patient, slot, booking_id="MQ-WAIT-0002")
    db.session.commit()

    other = _login(app, base.other_patient.email)
    response = other.get(f"/api/appointments/{appointment.booking_id}/wait")
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "FORBIDDEN"


def test_wait_api_unknown_booking_is_json_404(app, base):
    patient = _login(app, base.patient.email)
    response = patient.get("/api/appointments/MQ-19700101-0000/wait")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_wait_api_reports_live_queue_for_today(app, base):
    today = date.today()
    today_slot = make_slot(
        base.doctor, day=today, start=time(11, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(
        base.patient, today_slot, queue_position=2, estimated_wait_minutes=15
    )
    earlier_slot = make_slot(
        base.doctor, day=today, start=time(9, 0), status=SlotStatus.BOOKED
    )
    make_appointment(base.other_patient, earlier_slot, booking_id="MQ-LIVE-AHEAD")
    waiting_service.set_delay_minutes(base.doctor.id, 5, today)
    db.session.commit()

    patient = _login(app, base.patient.email)
    response = patient.get(f"/api/appointments/{appointment.booking_id}/wait")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["patients_ahead"] == 1
    assert payload["queue_position"] == 2
    assert payload["delay_minutes"] == 5
    assert payload["estimated_wait_minutes"] == base.doctor.avg_consult_minutes + 5
