"""Deterministic data factories for the MediQueue test suite.

Every helper adds objects to the current SQLAlchemy session and flushes (but
does not commit) so a single ``db.session.commit()`` can persist a graph. Tests
that need isolation should call ``db.session.commit()`` themselves or use the
provided fixtures.
"""
import itertools
from datetime import date, datetime, time, timedelta

from app.constants import AppointmentStatus, Roles, SlotStatus
from app.extensions import db
from app.models.appointment import Appointment
from app.models.department import Department
from app.models.doctor import Doctor, DoctorSchedule
from app.models.slot import Slot
from app.models.user import PatientProfile, User

TEST_PASSWORD = "Secret123"

_sequence = itertools.count(1)


def unique(prefix="x"):
    return f"{prefix}{next(_sequence)}"


def future_day(days=2):
    """A deterministic future date that stays valid whenever tests run."""
    return date.today() + timedelta(days=days)


def make_user(
    full_name="Asha Verma",
    email=None,
    role=Roles.PATIENT,
    password=TEST_PASSWORD,
    phone="+91 99887 22001",
    is_active=True,
    with_profile=None,
):
    email = email or f"{unique('user')}@example.test"
    user = User(
        role=role,
        full_name=full_name,
        email=email.lower(),
        phone=phone,
        is_active=is_active,
    )
    user.set_password(password)
    if with_profile is None:
        with_profile = role == Roles.PATIENT
    if with_profile:
        user.patient_profile = PatientProfile(gender="Female", blood_group="O+")
    db.session.add(user)
    db.session.flush()
    return user


def make_department(name=None, is_active=True, **kwargs):
    name = name or f"Department {unique()}"
    department = Department(
        name=name,
        slug=name.lower().replace(" ", "-") + f"-{next(_sequence)}",
        description=kwargs.pop("description", f"{name} description"),
        icon=kwargs.pop("icon", "fa-hospital"),
        is_active=is_active,
    )
    for key, value in kwargs.items():
        setattr(department, key, value)
    db.session.add(department)
    db.session.flush()
    return department


def make_doctor(
    department,
    full_name="Arjun Mehta",
    email=None,
    specialization="Interventional Cardiologist",
    avg_consult_minutes=15,
    consultation_fee=500,
    is_active=True,
    **kwargs,
):
    user = make_user(
        full_name=full_name,
        email=email or f"dr.{unique('doc')}@example.test",
        role=Roles.DOCTOR,
        with_profile=False,
        is_active=is_active,
    )
    doctor = Doctor(
        user=user,
        department=department,
        specialization=specialization,
        qualification=kwargs.pop("qualification", "MBBS, MD"),
        experience_years=kwargs.pop("experience_years", 10),
        consultation_fee=consultation_fee,
        room_no=kwargs.pop("room_no", "C-204"),
        avg_consult_minutes=avg_consult_minutes,
        is_active=is_active,
    )
    for key, value in kwargs.items():
        setattr(doctor, key, value)
    db.session.add(doctor)
    db.session.flush()
    return doctor


def make_schedule(
    doctor,
    weekday=None,
    start=time(9, 0),
    end=time(10, 0),
    duration=20,
    max_patients=None,
    is_active=True,
):
    weekday = weekday if weekday is not None else future_day(1).weekday()
    schedule = DoctorSchedule(
        doctor=doctor,
        weekday=weekday,
        start_time=start,
        end_time=end,
        slot_duration_minutes=duration,
        max_patients=max_patients,
        is_active=is_active,
    )
    db.session.add(schedule)
    db.session.flush()
    return schedule


def make_slot(
    doctor,
    day=None,
    start=time(10, 0),
    minutes=20,
    status=SlotStatus.AVAILABLE,
    fee=None,
):
    day = day or future_day()
    start_dt = datetime.combine(day, start)
    end_dt = start_dt + timedelta(minutes=minutes)
    slot = Slot(
        doctor=doctor,
        slot_date=day,
        start_time=start_dt.time(),
        end_time=end_dt.time(),
        status=status,
        fee=doctor.consultation_fee if fee is None else fee,
    )
    db.session.add(slot)
    db.session.flush()
    return slot


def make_appointment(
    patient,
    slot,
    status=AppointmentStatus.CONFIRMED,
    reason="Routine check-up",
    booking_id=None,
    queue_position=1,
    estimated_wait_minutes=0,
):
    """Create an appointment directly, bypassing the booking service.

    Used for arranging a pre-existing queue. The slot is marked bookable only
    when the caller supplied an already-booked slot; this helper does not change
    slot status so tests can arrange inconsistent fixtures deliberately.
    """
    booking_id = booking_id or f"MQ-{slot.slot_date:%Y%m%d}-{next(_sequence):04d}"
    appointment = Appointment(
        booking_id=booking_id,
        patient=patient,
        doctor_id=slot.doctor_id,
        slot=slot,
        appointment_date=slot.slot_date,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status=status,
        reason_for_visit=reason,
        fee=slot.fee if slot.fee is not None else slot.doctor.consultation_fee,
        queue_position=queue_position,
        estimated_wait_minutes=estimated_wait_minutes,
    )
    db.session.add(appointment)
    db.session.flush()
    return appointment


def book_slot(doctor, day=None, start=time(10, 0), minutes=20):
    """Convenience: create an AVAILABLE slot for a doctor."""
    return make_slot(doctor, day=day, start=start, minutes=minutes)
