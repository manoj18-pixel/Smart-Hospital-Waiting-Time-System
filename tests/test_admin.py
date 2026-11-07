"""T15, T16 & T18 — Admin dashboard, CRUD, filters and moderation."""
from datetime import date, time, timedelta

from app.constants import AppointmentStatus, Roles, SlotStatus
from app.extensions import db
from app.models.appointment import Appointment
from app.models.department import Department
from app.models.doctor import Doctor, DoctorSchedule
from app.models.slot import Slot
from app.models.user import User

from .factories import (
    TEST_PASSWORD,
    future_day,
    make_appointment,
    make_department,
    make_doctor,
    make_slot,
)


def _login(app, email, password=TEST_PASSWORD):
    client = app.test_client()
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302
    return client


def test_admin_dashboard_kpis_and_charts(app, base):
    today = date.today()
    first_slot = make_slot(base.doctor, day=today, start=time(9, 0), status=SlotStatus.BOOKED)
    second_slot = make_slot(base.doctor, day=today, start=time(9, 30), status=SlotStatus.BOOKED)
    make_appointment(base.patient, first_slot, booking_id="MQ-KPI-1")
    make_appointment(base.other_patient, second_slot, booking_id="MQ-KPI-2")
    db.session.commit()

    client = _login(app, base.admin.email)
    response = client.get("/admin/dashboard")
    assert response.status_code == 200
    assert b"bookingsChart" in response.data
    assert b"utilChart" in response.data

    response = client.get("/admin/api/stats")
    assert response.status_code == 200
    payload = response.get_json()
    kpis = payload["kpis"]
    assert kpis["total_patients"] == 2
    assert kpis["total_doctors"] == 2
    assert kpis["total_departments"] == 2
    assert kpis["appointments_today"] == 2
    assert kpis["total_appointments"] == 2
    assert kpis["cancellation_rate"] == 0
    assert len(payload["bookings_per_day"]["labels"]) == 7
    assert len(payload["slot_utilization"]["values"]) == 2
    assert "Cardiology" in payload["department_load"]["labels"]
    # Peak-hour buckets are hourly, so both 09:00 and 09:30 count towards 09:00.
    assert payload["peak_hours"]["labels"] == ["09:00"]
    assert payload["peak_hours"]["values"] == [2]


def test_non_admin_cannot_reach_admin_area(app, base):
    patient = _login(app, base.patient.email)
    assert patient.get("/admin/dashboard").status_code == 403
    assert patient.get("/admin/api/stats").status_code == 403

    doctor = _login(app, base.doctor.user.email)
    assert doctor.get("/admin/dashboard").status_code == 403


def test_anonymous_admin_access_redirects_to_login(app):
    response = app.test_client().get("/admin/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_department_create_edit_and_toggle(app, base):
    client = _login(app, base.admin.email)

    response = client.post(
        "/admin/departments/new",
        data={
            "name": "Dermatology",
            "description": "Skin care",
            "icon": "fa-allergies",
            "floor": "2nd floor",
            "phone_ext": "205",
            "is_active": "y",
        },
    )
    assert response.status_code == 302
    department = Department.query.filter_by(name="Dermatology").one()
    assert department.slug == "dermatology"
    assert department.is_active is True

    response = client.post(
        f"/admin/departments/{department.id}/edit",
        data={
            "name": "Skin & Hair",
            "description": "Dermatology and trichology",
            "icon": "fa-allergies",
            "floor": "2nd floor",
            "phone_ext": "205",
            "is_active": "y",
        },
    )
    assert response.status_code == 302
    db.session.expire_all()
    department = db.session.get(Department, department.id)
    assert department.name == "Skin & Hair"
    assert department.slug == "skin-hair"

    response = client.post(f"/admin/departments/{department.id}/toggle")
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(Department, department.id).is_active is False


def test_department_validation_rejects_blank_name(app, base):
    client = _login(app, base.admin.email)
    response = client.post(
        "/admin/departments/new", data={"name": "", "is_active": "y"}
    )
    assert response.status_code == 200
    assert Department.query.filter_by(name="").first() is None


def test_doctor_create_with_login_and_schedule(app, base):
    client = _login(app, base.admin.email)
    weekday = future_day(1).weekday()

    response = client.post(
        "/admin/doctors/new",
        data={
            "full_name": "Nisha Patel",
            "email": "dr.nisha@test.local",
            "phone": "+91 90000 11111",
            "password": "Doctor123",
            "department_id": base.department.id,
            "specialization": "Consultant Physician",
            "qualification": "MBBS, MD",
            "experience_years": "7",
            "consultation_fee": "650",
            "room_no": "G-010",
            "bio": "Friendly physician.",
            "avg_consult_minutes": "15",
            "is_active": "y",
        },
    )
    assert response.status_code == 302

    user = User.query.filter_by(email="dr.nisha@test.local").one()
    assert user.role == Roles.DOCTOR
    assert user.check_password("Doctor123")
    doctor = Doctor.query.filter_by(user_id=user.id).one()
    assert doctor.department_id == base.department.id
    assert response.headers["Location"].endswith(f"/admin/doctors/{doctor.id}/schedules")

    response = client.post(
        f"/admin/doctors/{doctor.id}/schedules",
        data={
            "weekday": str(weekday),
            "start_time": "09:00",
            "end_time": "10:00",
            "slot_duration_minutes": "20",
            "is_active": "y",
        },
    )
    assert response.status_code == 302
    assert DoctorSchedule.query.filter_by(doctor_id=doctor.id).count() == 1
    assert Slot.query.filter_by(doctor_id=doctor.id).count() > 0


def test_duplicate_doctor_email_is_rejected(app, base):
    client = _login(app, base.admin.email)
    before = Doctor.query.count()
    response = client.post(
        "/admin/doctors/new",
        data={
            "full_name": "Copy Cat",
            "email": base.doctor.email,
            "password": "Doctor123",
            "department_id": base.department.id,
            "specialization": "Cardiologist",
            "experience_years": "4",
            "consultation_fee": "500",
            "avg_consult_minutes": "15",
            "is_active": "y",
        },
    )
    assert response.status_code == 200
    assert b"already uses this email" in response.data
    assert Doctor.query.count() == before


def test_doctor_toggle_hides_them_from_patients(app, base):
    client = _login(app, base.admin.email)
    response = client.post(f"/admin/doctors/{base.doctor.id}/toggle")
    assert response.status_code == 302

    db.session.expire_all()
    assert db.session.get(Doctor, base.doctor.id).is_active is False
    assert db.session.get(User, base.doctor.user_id).is_active is False

    patient = _login(app, base.patient.email)
    doctors_page = patient.get(f"/patient/departments/{base.department.id}/doctors")
    assert b"Arjun Mehta" not in doctors_page.data


def test_patient_search_and_toggle(app, base):
    client = _login(app, base.admin.email)

    response = client.get("/admin/patients?q=Asha")
    assert response.status_code == 200
    assert b"Asha Verma" in response.data
    assert b"Ravi Kumar" not in response.data

    response = client.get("/admin/patients?q=ravi@test.local")
    assert b"Ravi Kumar" in response.data
    assert b"Asha Verma" not in response.data

    response = client.post(f"/admin/patients/{base.patient.id}/toggle")
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(User, base.patient.id).is_active is False


def test_appointment_filters_and_search(app, base):
    day_one = future_day(2)
    day_two = future_day(3)
    slot_one = make_slot(base.doctor, day=day_one, start=time(9, 0), status=SlotStatus.BOOKED)
    slot_two = make_slot(
        base.other_doctor, day=day_two, start=time(10, 0), status=SlotStatus.BOOKED
    )
    first = make_appointment(base.patient, slot_one, booking_id="MQ-FILTER-1")
    second = make_appointment(
        base.patient,
        slot_two,
        booking_id="MQ-FILTER-2",
        status=AppointmentStatus.CANCELLED,
    )
    db.session.commit()

    client = _login(app, base.admin.email)

    response = client.get("/admin/appointments?status=CONFIRMED")
    assert b"MQ-FILTER-1" in response.data
    assert b"MQ-FILTER-2" not in response.data

    response = client.get(f"/admin/appointments?doctor_id={base.other_doctor.id}")
    assert b"MQ-FILTER-2" in response.data
    assert b"MQ-FILTER-1" not in response.data

    response = client.get("/admin/appointments?q=FILTER-1")
    assert b"MQ-FILTER-1" in response.data
    assert b"MQ-FILTER-2" not in response.data

    response = client.get(f"/admin/appointments?date={day_one.isoformat()}")
    assert b"MQ-FILTER-1" in response.data
    assert b"MQ-FILTER-2" not in response.data


def test_admin_can_cancel_any_appointment(app, base):
    slot = make_slot(base.doctor, day=future_day(2), start=time(11, 0), status=SlotStatus.BOOKED)
    appointment = make_appointment(base.patient, slot, booking_id="MQ-ADMIN-CANCEL")
    db.session.commit()

    client = _login(app, base.admin.email)
    response = client.post(
        f"/admin/appointments/{appointment.id}/cancel",
        data={"reason": "Doctor unavailable"},
    )
    assert response.status_code == 302

    db.session.expire_all()
    updated = db.session.get(Appointment, appointment.id)
    assert updated.status == AppointmentStatus.CANCELLED
    assert updated.cancel_reason == "Doctor unavailable"
    assert db.session.get(Slot, slot.id).status == SlotStatus.AVAILABLE
