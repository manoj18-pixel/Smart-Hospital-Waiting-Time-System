"""Appointment booking, cancellation and queue transitions."""
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from ..constants import (
    ACTIVE_APPOINTMENT_STATUSES,
    AppointmentStatus,
    SlotStatus,
)
from ..extensions import db
from ..models.appointment import Appointment
from ..models.setting import Setting
from ..models.slot import Slot
from ..models.user import User
from . import audit_service, mail_service, waiting_service
from .slot_service import claim_slot, release_slot


class BookingError(Exception):
    def __init__(self, message, code="BOOKING_ERROR", status=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _setting_int(key, config_key, default):
    return Setting.get_int(key, current_app.config.get(config_key, default))


def _booking_id(day):
    prefix = f"MQ-{day:%Y%m%d}"
    count = Appointment.query.filter(Appointment.appointment_date == day).count()
    return f"{prefix}-{count + 1:04d}"


def create_booking(patient, slot_id, reason=None):
    """Create a booking with an atomic slot claim.

    The conditional UPDATE is issued before reading the slot. This avoids
    read-then-write upgrade deadlocks on SQLite while remaining correct on
    InnoDB, where the update locks the row.
    """
    patient_id = patient.id
    if db.engine.dialect.name == "sqlite":
        # Start a clean write transaction; the Flask-Login lookup may have
        # already opened a read transaction, which cannot be upgraded in WAL.
        db.session.rollback()

    claimed = claim_slot(slot_id)
    if not claimed:
        db.session.rollback()
        slot = db.session.get(Slot, slot_id)
        if slot is None:
            raise BookingError("That time slot does not exist.", "NOT_FOUND", 404)
        if slot.status == SlotStatus.BOOKED:
            raise BookingError(
                "This slot was just booked by another patient. Please choose another available slot.",
                "SLOT_TAKEN",
                409,
            )
        raise BookingError(
            "This slot is not available for booking.", "SLOT_UNAVAILABLE", 409
        )

    slot = db.session.get(Slot, slot_id)
    doctor = slot.doctor
    now = datetime.now()

    try:
        if not doctor or not doctor.is_active:
            raise BookingError("This doctor is not accepting appointments.", "DOCTOR_INACTIVE", 409)
        if slot.starts_at <= now:
            raise BookingError("This slot has already passed. Please pick another.", "SLOT_PASSED", 400)
        open_days = _setting_int("booking_open_days", "BOOKING_OPEN_DAYS", 30)
        if slot.slot_date > (now.date() + timedelta(days=open_days)):
            raise BookingError(
                f"Bookings open only {open_days} days in advance.", "WINDOW_CLOSED", 400
            )

        duplicate = Appointment.query.filter(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == slot.slot_date,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        ).first()
        if duplicate:
            raise BookingError(
                "You already have an appointment with this doctor on this date.",
                "ALREADY_BOOKED",
                409,
            )

        estimate = waiting_service.estimate_for_new_booking(
            doctor, slot.slot_date, slot.start_time
        )
        appointment = Appointment(
            booking_id=_booking_id(slot.slot_date),
            patient_id=patient_id,
            doctor_id=doctor.id,
            slot_id=slot.id,
            appointment_date=slot.slot_date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            status=AppointmentStatus.CONFIRMED,
            reason_for_visit=(reason or "").strip() or None,
            fee=slot.fee if slot.fee is not None else doctor.consultation_fee,
            queue_position=estimate["queue_position"],
            estimated_wait_minutes=estimate["estimated_wait_minutes"],
        )
        db.session.add(appointment)
        db.session.commit()
    except BookingError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        text = str(exc.orig).lower()
        if "slot" in text or "appointments.slot_id" in text:
            raise BookingError(
                "This slot was just booked by another patient. Please choose another available slot.",
                "SLOT_TAKEN",
                409,
            ) from exc
        raise BookingError(
            "We could not complete the booking. Please try again.", "BOOKING_FAILED", 409
        ) from exc

    audit_service.log(
        "booking_created",
        "appointment",
        appointment.id,
        {"booking_id": appointment.booking_id, "slot_id": slot.id},
        actor=db.session.get(User, patient_id),
    )
    try:
        mail_service.send_booking_confirmation(appointment)
    except Exception:  # pragma: no cover - mail failures are non-fatal
        db.session.rollback()
    return appointment


def cancel_booking(appointment, actor, reason, is_admin=False):
    if appointment.status == AppointmentStatus.CANCELLED:
        raise BookingError("This appointment is already cancelled.", "ALREADY_CANCELLED", 409)
    if appointment.status not in ACTIVE_APPOINTMENT_STATUSES:
        raise BookingError(
            "Completed or missed appointments cannot be cancelled.",
            "NOT_CANCELLABLE",
            409,
        )

    cutoff = _setting_int(
        "cancellation_cutoff_hours", "CANCELLATION_CUTOFF_HOURS", 2
    )
    if not is_admin and not appointment.cancellable(cutoff):
        raise BookingError(
            f"Cancellations are allowed up to {cutoff} hours before the appointment.",
            "CANCEL_CUTOFF_PASSED",
            409,
        )

    if not is_admin:
        max_cancels = _setting_int(
            "max_cancellations_per_30_days", "MAX_CANCELLATIONS_PER_30_DAYS", 3
        )
        since = datetime.utcnow() - timedelta(days=30)
        recent = Appointment.query.filter(
            Appointment.patient_id == appointment.patient_id,
            Appointment.status == AppointmentStatus.CANCELLED,
            Appointment.cancelled_at >= since,
        ).count()
        if recent >= max_cancels:
            raise BookingError(
                f"You have reached the limit of {max_cancels} cancellations in 30 days. Please contact the hospital.",
                "CANCEL_LIMIT",
                409,
            )

    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = datetime.utcnow()
    appointment.cancelled_by = getattr(actor, "id", None)
    appointment.cancel_reason = (reason or "").strip() or "Not specified"
    released = False
    if appointment.slot and appointment.slot.starts_at > datetime.now():
        released = release_slot(appointment.slot_id)
    db.session.commit()

    audit_service.log(
        "booking_cancelled",
        "appointment",
        appointment.id,
        {"booking_id": appointment.booking_id, "reason": appointment.cancel_reason},
        actor=actor,
    )
    try:
        mail_service.send_cancellation(
            appointment, "hospital" if is_admin else "patient"
        )
    except Exception:  # pragma: no cover
        db.session.rollback()
    return appointment, released


def check_in(appointment):
    if appointment.status != AppointmentStatus.CONFIRMED:
        raise BookingError("Only confirmed appointments can be checked in.", "INVALID_STATE", 409)
    appointment.status = AppointmentStatus.CHECKED_IN
    appointment.checked_in_at = datetime.utcnow()
    db.session.commit()
    audit_service.log("patient_checked_in", "appointment", appointment.id)
    return appointment


def complete(appointment):
    if appointment.status not in (
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.IN_CONSULTATION,
        AppointmentStatus.CONFIRMED,
    ):
        raise BookingError("This appointment cannot be completed.", "INVALID_STATE", 409)
    appointment.status = AppointmentStatus.COMPLETED
    appointment.completed_at = datetime.utcnow()
    doctor = appointment.doctor
    if appointment.checked_in_at:
        actual = (datetime.utcnow() - appointment.checked_in_at).total_seconds() / 60
        actual = max(5, min(60, actual))
        doctor.avg_consult_minutes = max(
            5, min(60, round(0.8 * doctor.avg_consult_minutes + 0.2 * actual))
        )
    db.session.commit()
    audit_service.log("patient_completed", "appointment", appointment.id)
    return appointment


def mark_no_show(appointment):
    if appointment.status not in (
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
    ):
        raise BookingError("This appointment cannot be marked as no-show.", "INVALID_STATE", 409)
    appointment.status = AppointmentStatus.NO_SHOW
    db.session.commit()
    audit_service.log("patient_no_show", "appointment", appointment.id)
    return appointment
