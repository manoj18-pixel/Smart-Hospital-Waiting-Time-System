"""JSON endpoints used by the booking UI and dashboards."""
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required

from ..constants import Roles
from ..extensions import db
from ..models.appointment import Appointment
from ..models.doctor import Doctor
from ..models.setting import Setting
from ..services import schedule_service, slot_service, waiting_service
from ..utils.time_utils import humanize_minutes

bp = Blueprint("api", __name__, url_prefix="/api")


def _doctor_or_404(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if doctor is None or not doctor.is_active:
        abort(404)
    return doctor


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@bp.get("/doctors/<int:doctor_id>/slots")
def doctor_slots(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    day = _parse_date(request.args.get("date")) or date.today()
    open_days = Setting.get_int("booking_open_days", 30)
    if day < date.today() or day > date.today() + timedelta(days=open_days):
        return (
            jsonify(
                ok=False,
                error={
                    "code": "DATE_OUT_OF_RANGE",
                    "message": f"Choose a date within the next {open_days} days.",
                },
            ),
            400,
        )
    schedule_service.generate_slots(doctor, days=open_days)
    payload = slot_service.serialize_slots(doctor.id, day)
    payload["is_working_day"] = len(payload["slots"]) > 0
    return jsonify(ok=True, **payload)


@bp.get("/doctors/<int:doctor_id>/next-available")
def next_available(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    from_date = _parse_date(request.args.get("from")) or date.today()
    schedule_service.generate_slots(doctor, days=Setting.get_int("booking_open_days", 30))
    slot = schedule_service.next_available(doctor, from_date)
    if slot is None:
        return jsonify(ok=True, available=False, slot=None)
    return jsonify(
        ok=True,
        available=True,
        slot={
            "id": slot.id,
            "date": slot.slot_date.isoformat(),
            "start": slot.start_time.strftime("%H:%M"),
            "end": slot.end_time.strftime("%H:%M"),
        },
    )


@bp.get("/appointments/<booking_id>/wait")
@login_required
def appointment_wait(booking_id):
    appointment = Appointment.query.filter_by(booking_id=booking_id).first()
    if appointment is None:
        abort(404)
    allowed = current_user.role == Roles.ADMIN or appointment.patient_id == current_user.id
    if current_user.role == Roles.DOCTOR:
        allowed = bool(current_user.doctor and current_user.doctor.id == appointment.doctor_id)
    if not allowed:
        abort(403)

    if appointment.appointment_date == date.today():
        estimate = waiting_service.live_wait(appointment)
    else:
        estimate = {
            "patients_ahead": max(0, (appointment.queue_position or 1) - 1),
            "queue_position": appointment.queue_position or 1,
            "estimated_wait_minutes": appointment.estimated_wait_minutes or 0,
            "delay_minutes": 0,
            "avg_consult_minutes": appointment.doctor.avg_consult_minutes,
        }
    return jsonify(
        ok=True,
        booking_id=appointment.booking_id,
        status=appointment.status,
        **estimate,
        label=humanize_minutes(estimate["estimated_wait_minutes"]),
        updated_at=datetime.now().isoformat(timespec="seconds"),
    )
