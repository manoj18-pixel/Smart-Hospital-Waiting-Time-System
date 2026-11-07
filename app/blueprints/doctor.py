"""Doctor dashboard, daily schedule and queue actions."""
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..constants import AppointmentStatus
from ..extensions import db
from ..forms import DelayForm
from ..models.appointment import Appointment
from ..services import booking_service, waiting_service
from ..utils.decorators import doctor_required
from ..utils.time_utils import format_date, humanize_minutes

bp = Blueprint("doctor", __name__, url_prefix="/doctor")


def _current_doctor():
    doctor = getattr(current_user, "doctor", None)
    if doctor is None or not doctor.is_active:
        abort(404)
    return doctor


def _owned_appointment(appointment_id):
    doctor = _current_doctor()
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None:
        abort(404)
    if appointment.doctor_id != doctor.id:
        abort(403)
    return appointment


def _parse_date(value):
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def _day_context(doctor, day):
    queue = waiting_service.doctor_queue(doctor.id, day)
    stats = {
        "total": len(queue),
        "completed": sum(1 for a in queue if a.status == AppointmentStatus.COMPLETED),
        "waiting": sum(
            1
            for a in queue
            if a.status in (AppointmentStatus.CONFIRMED, AppointmentStatus.CHECKED_IN)
        ),
        "checked_in": sum(1 for a in queue if a.status == AppointmentStatus.CHECKED_IN),
        "no_show": sum(1 for a in queue if a.status == AppointmentStatus.NO_SHOW),
    }
    current = next(
        (
            a
            for a in queue
            if a.status in (AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_CONSULTATION)
        ),
        None,
    )
    next_patient = next(
        (
            a
            for a in queue
            if a.status == AppointmentStatus.CONFIRMED and a.start_time >= datetime.now().time()
        ),
        None,
    )
    waits = {}
    for appointment in queue:
        if appointment.is_active:
            waits[appointment.id] = waiting_service.live_wait(appointment)
    return {
        "queue": queue,
        "stats": stats,
        "current": current,
        "next_patient": next_patient,
        "waits": waits,
    }


@bp.get("/dashboard")
@doctor_required
def dashboard():
    doctor = _current_doctor()
    today = date.today()
    context = _day_context(doctor, today)
    delay = waiting_service.delay_minutes(doctor.id, today)
    return render_template(
        "doctor/dashboard.html",
        doctor=doctor,
        day=today,
        day_label=format_date(today),
        delay=delay,
        delay_form=DelayForm(delay_minutes=delay),
        **context,
    )


@bp.route("/schedule", methods=["GET"])
@doctor_required
def schedule():
    doctor = _current_doctor()
    day = _parse_date(request.args.get("date"))
    context = _day_context(doctor, day)
    waits = context.pop("waits")
    wait_labels = {
        appointment_id: humanize_minutes(wait["estimated_wait_minutes"])
        for appointment_id, wait in waits.items()
    }
    delay = waiting_service.delay_minutes(doctor.id, day)
    return render_template(
        "doctor/schedule.html",
        doctor=doctor,
        day=day,
        day_label=format_date(day),
        previous_day=day - timedelta(days=1),
        next_day=day + timedelta(days=1),
        delay=delay,
        delay_form=DelayForm(delay_minutes=delay),
        waits=waits,
        wait_labels=wait_labels,
        **context,
    )


@bp.post("/appointments/<int:appointment_id>/checkin")
@doctor_required
def checkin(appointment_id):
    appointment = _owned_appointment(appointment_id)
    try:
        booking_service.check_in(appointment)
        flash("Patient checked in.", "success")
    except booking_service.BookingError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("doctor.schedule", date=appointment.appointment_date.isoformat()))


@bp.post("/appointments/<int:appointment_id>/complete")
@doctor_required
def complete(appointment_id):
    appointment = _owned_appointment(appointment_id)
    try:
        booking_service.complete(appointment)
        flash("Consultation marked complete. Waiting times updated.", "success")
    except booking_service.BookingError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("doctor.schedule", date=appointment.appointment_date.isoformat()))


@bp.post("/appointments/<int:appointment_id>/no-show")
@doctor_required
def no_show(appointment_id):
    appointment = _owned_appointment(appointment_id)
    try:
        booking_service.mark_no_show(appointment)
        flash("Appointment marked as no-show.", "warning")
    except booking_service.BookingError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("doctor.schedule", date=appointment.appointment_date.isoformat()))


@bp.post("/delay")
@doctor_required
def set_delay():
    doctor = _current_doctor()
    form = DelayForm()
    day = _parse_date(request.form.get("date"))
    if form.validate_on_submit():
        waiting_service.set_delay_minutes(doctor.id, form.delay_minutes.data, day)
        flash("Running-late time updated. Patient estimates refreshed.", "success")
    else:
        flash("Please enter a delay between 0 and 180 minutes.", "danger")
    return redirect(url_for("doctor.schedule", date=day.isoformat()))
