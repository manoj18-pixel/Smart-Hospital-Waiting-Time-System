"""Data-model helpers, relationships and database constraints."""
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.constants import AppointmentStatus, SlotStatus
from app.extensions import db
from app.models.appointment import Appointment
from app.models.doctor import ScheduleException
from app.models.slot import Slot

from .factories import (
    future_day,
    make_appointment,
    make_doctor,
    make_schedule,
    make_slot,
    make_user,
)


def test_user_password_helpers_and_initials(app, base):
    assert base.patient.password_hash != "Secret123"
    assert base.patient.check_password("Secret123")
    assert not base.patient.check_password("wrong")
    assert base.patient.first_name == "Asha"
    assert base.patient.initials == "AV"
    assert "asha@test.local" in repr(base.patient)


def test_user_initials_and_first_name_handle_single_name(app):
    user = make_user("Madonna", "madonna@test.local")
    db.session.commit()
    assert user.first_name == "Madonna"
    assert user.initials == "M"


def test_doctor_name_email_and_initials(app, base):
    doctor = base.doctor
    assert doctor.name == "Arjun Mehta"
    assert doctor.email == "dr.arjun@test.local"
    assert doctor.initials == "AM"
    assert "Arjun Mehta" in repr(doctor)


def test_department_counts_only_active_doctors(app, base):
    assert base.department.doctor_count == 1

    make_doctor(base.department, full_name="Inactive Doc", is_active=False)
    db.session.commit()

    assert base.department.doctor_count == 1
    assert [doctor.name for doctor in base.department.active_doctors] == ["Arjun Mehta"]
    assert "Cardiology" in repr(base.department)


def test_schedule_weekday_and_exception_windows(app, base):
    schedule = make_schedule(base.doctor, weekday=0)
    full_day = ScheduleException(
        doctor=base.doctor, exception_date=future_day(), is_closed=True
    )
    partial = ScheduleException(
        doctor=base.doctor,
        exception_date=future_day(2),
        is_closed=False,
        start_time=time(9, 0),
        end_time=time(10, 0),
    )
    db.session.add_all([full_day, partial])
    db.session.commit()

    assert schedule.weekday_name == "Monday"
    assert full_day.covers(time(11, 0), time(11, 20))
    assert partial.covers(time(9, 30), time(9, 50))
    assert not partial.covers(time(10, 0), time(10, 20))


def test_slot_time_properties(app, base):
    day = future_day()
    slot = make_slot(base.doctor, day=day, start=time(10, 0))
    assert slot.starts_at == datetime.combine(day, time(10, 0))
    assert slot.is_available is True
    assert slot.is_past is False

    past = make_slot(
        base.doctor, day=date.today() - timedelta(days=1), start=time(10, 0)
    )
    assert past.is_available is False
    assert past.is_past is True


def test_slot_defaults_to_available(app, base):
    slot = Slot(
        doctor=base.doctor,
        slot_date=future_day(5),
        start_time=time(8, 0),
        end_time=time(8, 20),
    )
    db.session.add(slot)
    db.session.commit()
    assert slot.status == SlotStatus.AVAILABLE


def test_appointment_time_and_status_helpers(app, base):
    day = future_day(2)
    slot = make_slot(
        base.doctor, day=day, start=time(10, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(base.patient, slot)
    db.session.commit()

    assert appointment.starts_at == datetime.combine(day, time(10, 0))
    assert appointment.ends_at == datetime.combine(day, time(10, 20))
    assert appointment.is_active
    assert appointment.is_upcoming
    assert appointment.cancellable()
    assert not appointment.is_today


def test_near_term_appointment_is_not_cancellable(app, base):
    soon = datetime.now() + timedelta(minutes=30)
    slot = make_slot(
        base.doctor,
        day=soon.date(),
        start=soon.time(),
        minutes=10,
        status=SlotStatus.BOOKED,
    )
    appointment = make_appointment(base.other_patient, slot)
    db.session.commit()

    assert appointment.is_active
    assert not appointment.cancellable()


def test_finished_appointments_are_not_active(app, base):
    for status, offset in (
        (AppointmentStatus.COMPLETED, 1),
        (AppointmentStatus.CANCELLED, 2),
        (AppointmentStatus.NO_SHOW, 3),
    ):
        slot = make_slot(
            base.doctor,
            day=future_day(3 + offset),
            start=time(9, 0),
            status=SlotStatus.BOOKED,
        )
        appointment = make_appointment(base.patient, slot, status=status)
        assert not appointment.is_active
    db.session.commit()


def test_duplicate_doctor_slot_is_rejected(app, base):
    day = future_day()
    make_slot(base.doctor, day=day, start=time(10, 0))
    with pytest.raises(IntegrityError):
        make_slot(base.doctor, day=day, start=time(10, 0))
    db.session.rollback()


def test_slot_window_check_constraint(app, base):
    slot = Slot(
        doctor=base.doctor,
        slot_date=future_day(4),
        start_time=time(10, 0),
        end_time=time(9, 0),
        status=SlotStatus.AVAILABLE,
    )
    db.session.add(slot)
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_appointment_cannot_reuse_a_slot(app, base):
    slot = make_slot(
        base.doctor, day=future_day(), start=time(11, 0), status=SlotStatus.BOOKED
    )
    make_appointment(base.patient, slot)

    with pytest.raises(IntegrityError):
        make_appointment(base.other_patient, slot)
    db.session.rollback()


def test_invalid_appointment_status_is_rejected(app, base):
    slot = make_slot(
        base.doctor, day=future_day(3), start=time(12, 0), status=SlotStatus.BOOKED
    )
    with pytest.raises(IntegrityError):
        make_appointment(base.patient, slot, status="BOGUS")
    db.session.rollback()


def test_slot_and_appointment_backrefs_are_linked(app, base):
    slot = make_slot(
        base.doctor, day=future_day(), start=time(13, 0), status=SlotStatus.BOOKED
    )
    appointment = make_appointment(base.patient, slot)
    slot_id = slot.id
    appointment_id = appointment.id
    db.session.commit()
    db.session.expire_all()

    loaded = db.session.get(Slot, slot_id)
    assert loaded.appointment is not None
    assert loaded.appointment.id == appointment_id
    assert loaded.appointment.patient_id == base.patient.id
    assert loaded.appointment.patient.id == base.patient.id
    assert "MQ-" in repr(loaded.appointment)
