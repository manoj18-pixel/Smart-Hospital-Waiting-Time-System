"""Estimated waiting-time and queue-position calculations."""
from datetime import datetime

from ..constants import AppointmentStatus, QUEUE_STATUSES
from ..extensions import db
from ..models.appointment import Appointment
from ..models.setting import Setting


def delay_minutes(doctor_id, day=None):
    day = day or datetime.now().date()
    return Setting.get_int(f"delay:{doctor_id}:{day.isoformat()}", 0)


def set_delay_minutes(doctor_id, minutes, day=None):
    day = day or datetime.now().date()
    Setting.set(f"delay:{doctor_id}:{day.isoformat()}", int(minutes))
    # The request session is discarded at teardown, so persist the change here
    # rather than relying on a later commit.
    db.session.commit()
    return int(minutes)


def patients_ahead(doctor_id, day, start_time, exclude_appointment_id=None):
    query = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == day,
        Appointment.start_time < start_time,
        Appointment.status.in_(QUEUE_STATUSES),
    )
    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)
    return query.count()


def estimate_for_new_booking(doctor, day, start_time):
    """Estimate shown on the confirmation page for a brand new booking."""
    ahead = patients_ahead(doctor.id, day, start_time)
    delay = delay_minutes(doctor.id, day)
    wait = ahead * int(doctor.avg_consult_minutes or 15) + delay
    return {
        "patients_ahead": ahead,
        "queue_position": ahead + 1,
        "estimated_wait_minutes": max(0, wait),
        "delay_minutes": delay,
        "avg_consult_minutes": int(doctor.avg_consult_minutes or 15),
    }


def live_wait(appointment):
    """Live estimate for an existing appointment on its day.

    "Ahead" means earlier in the scheduled queue, not merely earlier than the
    wall clock. Counting every past appointment as ahead made the last patient
    of a delayed clinic appear to have the whole queue in front of them.
    """
    doctor = appointment.doctor
    ahead = patients_ahead(
        doctor.id,
        appointment.appointment_date,
        appointment.start_time,
        exclude_appointment_id=appointment.id,
    )
    delay = delay_minutes(doctor.id, appointment.appointment_date)
    wait = max(0, ahead * int(doctor.avg_consult_minutes or 15) + delay)
    return {
        "patients_ahead": ahead,
        "queue_position": ahead + 1,
        "estimated_wait_minutes": wait,
        "delay_minutes": delay,
        "avg_consult_minutes": int(doctor.avg_consult_minutes or 15),
    }


def doctor_queue(doctor_id, day):
    return (
        Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == day,
            Appointment.status.in_(
                (
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.CHECKED_IN,
                    AppointmentStatus.IN_CONSULTATION,
                    AppointmentStatus.COMPLETED,
                    AppointmentStatus.NO_SHOW,
                )
            ),
        )
        .order_by(Appointment.start_time)
        .all()
    )
